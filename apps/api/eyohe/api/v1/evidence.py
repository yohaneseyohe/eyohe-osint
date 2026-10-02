from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from eyohe.api.deps import DB, Analyst, CurrentUser
from eyohe.core.enums import EvidenceType, ReviewState, SourceType
from eyohe.core.errors import NotFoundError, ValidationError
from eyohe.models.entities import Entity
from eyohe.models.evidence import Evidence, EvidenceArtifact
from eyohe.models.findings import Finding, FindingEvidence
from eyohe.schemas.common import Page
from eyohe.schemas.evidence import (
    ArtifactOut,
    EvidenceCreate,
    EvidenceDetail,
    EvidenceOut,
    ReviewRequest,
    SnapshotDetail,
    SnapshotOut,
    SourceDetail,
    SourceOut,
)
from eyohe.services import cases as case_service
from eyohe.services import evidence as ev_service
from eyohe.services.vault import get_vault

router = APIRouter(tags=["evidence"])


@router.get("/cases/{case_id}/evidence", response_model=Page[EvidenceOut])
async def list_evidence(
    case_id: str,
    _: CurrentUser,
    db: DB,
    evidence_type: str | None = None,
    review_state: str | None = None,
    confidence: str | None = None,
    source_id: uuid.UUID | None = None,
    collector: str | None = None,
    entity_id: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> Page[EvidenceOut]:
    case = await case_service.get_case(db, case_id)
    items, total = await ev_service.list_evidence(
        db,
        case.id,
        evidence_type=evidence_type,
        review_state=review_state,
        confidence=confidence,
        source_id=source_id,
        collector=collector,
        entity_id=entity_id,
        q=q,
        page=page,
        page_size=page_size,
    )
    return Page(items=[EvidenceOut.model_validate(e) for e in items], total=total, page=page, page_size=page_size)


@router.post("/cases/{case_id}/evidence", response_model=EvidenceDetail, status_code=status.HTTP_201_CREATED)
async def create_evidence(case_id: str, payload: EvidenceCreate, user: Analyst, db: DB) -> EvidenceDetail:
    """Analyst-created evidence (e.g. from the query playground or manual review)."""
    case = await case_service.get_case(db, case_id)
    source = None
    if payload.source_id:
        source = await ev_service.get_source(db, payload.source_id)
    elif payload.source_url:
        source = await ev_service.upsert_source(
            db,
            case.id,
            url=payload.source_url,
            source_type=SourceType.WEBSITE,
            collector="analyst",
            tier=5,
            reliability_note="Added manually by analyst; tier not assessed.",
        )
    try:
        etype = EvidenceType(payload.evidence_type)
    except ValueError as exc:
        raise ValidationError(f"Unknown evidence type {payload.evidence_type}") from exc
    snap = await ev_service.latest_snapshot(db, source.id) if source else None
    ev = await ev_service.create_evidence(
        db,
        case.id,
        claim=payload.claim,
        evidence_type=etype,
        collector="analyst",
        source=source,
        snapshot=snap,
        excerpt=payload.excerpt,
        context=payload.context,
        observed_at=payload.observed_at,
        collection_method=f"manual:{user.username}",
    )
    if payload.entity_ids:
        await ev_service.link_entities(db, ev, payload.entity_ids)
        for eid in payload.entity_ids:
            ent = await db.get(Entity, eid)
            if ent and ent.case_id == case.id:
                ids = list(ent.evidence_ids or [])
                if str(ev.id) not in ids:
                    ent.evidence_ids = [*ids, str(ev.id)]
                    ent.source_count = len(ent.evidence_ids)
    await case_service.refresh_counts(db, case.id)
    await db.commit()
    return await _evidence_detail(db, ev.id)


async def _evidence_detail(db, ev_id: uuid.UUID) -> EvidenceDetail:  # type: ignore[no-untyped-def]
    ev = await ev_service.get_evidence(db, ev_id)
    out = EvidenceDetail(**EvidenceOut.model_validate(ev).model_dump())
    if ev.source_id:
        out.source = SourceOut.model_validate(await ev_service.get_source(db, ev.source_id))
    arts = (await db.execute(select(EvidenceArtifact).where(EvidenceArtifact.evidence_id == ev.id))).scalars()
    out.artifacts = [ArtifactOut.model_validate(a) for a in arts]
    if ev.entity_ids:
        ids = [uuid.UUID(x) for x in ev.entity_ids]
        ents = (await db.execute(select(Entity).where(Entity.id.in_(ids)))).scalars()
        out.entities = [
            {"id": str(e.id), "display_id": e.display_id, "type": e.type, "value": e.value, "label": e.label}
            for e in ents
        ]
    rows = await db.execute(
        select(Finding.id, Finding.display_id, Finding.title, Finding.confidence, FindingEvidence.role)
        .join(FindingEvidence, FindingEvidence.finding_id == Finding.id)
        .where(FindingEvidence.evidence_id == ev.id)
    )
    out.findings = [
        {"id": str(r[0]), "display_id": r[1], "title": r[2], "confidence": r[3], "role": r[4]} for r in rows
    ]
    return out


@router.get("/evidence/{evidence_id}", response_model=EvidenceDetail)
async def get_evidence(evidence_id: str, _: CurrentUser, db: DB) -> EvidenceDetail:
    ev = await ev_service.get_evidence(db, evidence_id)
    return await _evidence_detail(db, ev.id)


@router.post("/evidence/{evidence_id}/review", response_model=EvidenceDetail)
async def review_evidence(evidence_id: str, payload: ReviewRequest, user: Analyst, db: DB) -> EvidenceDetail:
    ev = await ev_service.get_evidence(db, evidence_id)
    await ev_service.review_evidence(db, ev, user, ReviewState(payload.state), payload.note)
    # Re-verify dependants so confidence stays consistent.
    from eyohe.verification.service import verify_case

    await verify_case(db, ev.case_id)
    await db.commit()
    return await _evidence_detail(db, ev.id)


@router.get("/evidence/{evidence_id}/artifacts/{artifact_id}")
async def download_artifact(evidence_id: str, artifact_id: uuid.UUID, _: CurrentUser, db: DB) -> FileResponse:
    ev = await ev_service.get_evidence(db, evidence_id)
    art = await db.get(EvidenceArtifact, artifact_id)
    if art is None or art.evidence_id != ev.id:
        raise NotFoundError("Artifact not found.")
    path = get_vault().resolve(art.path)
    if not path.exists():
        raise NotFoundError("Artifact file missing from vault.")
    return FileResponse(path, media_type=art.mime_type, filename=path.name)


@router.get("/cases/{case_id}/sources", response_model=Page[SourceOut])
async def list_sources(
    case_id: str,
    _: CurrentUser,
    db: DB,
    source_type: str | None = None,
    collector: str | None = None,
    max_tier: int | None = Query(default=None, ge=1, le=5),
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> Page[SourceOut]:
    case = await case_service.get_case(db, case_id)
    items, total = await ev_service.list_sources(
        db,
        case.id,
        source_type=source_type,
        collector=collector,
        max_tier=max_tier,
        q=q,
        page=page,
        page_size=page_size,
    )
    return Page(items=[SourceOut.model_validate(s) for s in items], total=total, page=page, page_size=page_size)


@router.get("/sources", response_model=Page[SourceOut])
async def list_all_sources(
    _: CurrentUser, db: DB, q: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500)
) -> Page[SourceOut]:
    from eyohe.models.sources import Source

    stmt = select(Source)
    if q:
        stmt = stmt.where(Source.url.ilike(f"%{q}%") | Source.title.ilike(f"%{q}%"))
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await db.execute(stmt.order_by(Source.collected_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).scalars()
    return Page(items=[SourceOut.model_validate(s) for s in rows], total=total, page=page, page_size=page_size)


@router.get("/sources/{source_id}", response_model=SourceDetail)
async def get_source(source_id: str, _: CurrentUser, db: DB) -> SourceDetail:
    src = await ev_service.get_source(db, source_id)
    await db.refresh(src, attribute_names=["snapshots"])
    out = SourceDetail(**SourceOut.model_validate(src).model_dump())
    out.snapshots = [SnapshotOut.model_validate(s) for s in src.snapshots]
    out.evidence_count = int(
        (await db.execute(select(func.count()).select_from(Evidence).where(Evidence.source_id == src.id))).scalar_one()
    )
    return out


@router.get("/sources/{source_id}/snapshots/{snapshot_id}", response_model=SnapshotDetail)
async def get_snapshot(source_id: str, snapshot_id: uuid.UUID, _: CurrentUser, db: DB) -> SnapshotDetail:
    from eyohe.models.sources import SourceSnapshot

    src = await ev_service.get_source(db, source_id)
    snap = await db.get(SourceSnapshot, snapshot_id)
    if snap is None or snap.source_id != src.id:
        raise NotFoundError("Snapshot not found.")
    return SnapshotDetail.model_validate(snap)


@router.get("/sources/{source_id}/compare")
async def compare_snapshots(source_id: str, _: CurrentUser, db: DB) -> dict[str, Any]:
    """Diff the two most recent snapshots of a source (title/text changes)."""
    import difflib

    src = await ev_service.get_source(db, source_id)
    await db.refresh(src, attribute_names=["snapshots"])
    snaps = sorted(src.snapshots, key=lambda s: s.retrieved_at)
    if len(snaps) < 2:
        return {"changed": False, "message": "Fewer than two snapshots; nothing to compare."}
    a, b = snaps[-2], snaps[-1]
    diff = list(difflib.unified_diff(a.text_content.splitlines(), b.text_content.splitlines(), lineterm="", n=1))
    return {
        "changed": a.content_hash != b.content_hash,
        "from": a.retrieved_at,
        "to": b.retrieved_at,
        "title_changed": a.title != b.title,
        "old_title": a.title,
        "new_title": b.title,
        "diff": diff[:400],
    }


@router.post("/sources/{source_id}/screenshot", response_model=EvidenceDetail, status_code=status.HTTP_201_CREATED)
async def screenshot_source(source_id: str, user: Analyst, db: DB) -> EvidenceDetail:
    """Capture a public page screenshot into the vault and record it as SCREENSHOT evidence."""
    from eyohe.services.screenshot import capture

    src = await ev_service.get_source(db, source_id)
    shot = await capture(src.case_id, src.url)
    ev = await ev_service.create_evidence(
        db,
        src.case_id,
        claim=(
            f"Screenshot of public page {src.url} captured at {shot['captured_at'].isoformat()} "
            f"({shot['browser']}, {shot['viewport']})"
        ),
        evidence_type=EvidenceType.SCREENSHOT,
        collector="screenshot",
        source=src,
        collection_method=f"chromium:{user.username}",
        structured={"sha256": shot["sha256"], "viewport": shot["viewport"], "browser": shot["browser"]},
        artifacts=[(get_vault().read(shot["path"]), "image/png", "screenshot")],
    )
    await db.commit()
    return await _evidence_detail(db, ev.id)
