from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from eyohe.api.deps import DB, Analyst, CurrentUser
from eyohe.core.enums import ReviewState
from eyohe.models.evidence import Evidence
from eyohe.models.sources import Source
from eyohe.schemas.common import Page
from eyohe.schemas.evidence import EvidenceOut
from eyohe.schemas.findings import AttachEvidence, FindingCreate, FindingDetail, FindingOut, TimelineOut, WhyOut
from eyohe.services import cases as case_service
from eyohe.services import evidence as ev_service
from eyohe.services import findings as f_service

router = APIRouter(tags=["findings"])


@router.get("/cases/{case_id}/findings", response_model=Page[FindingOut])
async def list_findings(
    case_id: str,
    _: CurrentUser,
    db: DB,
    confidence: str | None = None,
    review_state: str | None = None,
    category: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
) -> Page[FindingOut]:
    case = await case_service.get_case(db, case_id)
    items, total = await f_service.list_findings(
        db, case.id, confidence=confidence, review_state=review_state, category=category, page=page, page_size=page_size
    )
    return Page(items=[FindingOut.model_validate(f) for f in items], total=total, page=page, page_size=page_size)


@router.post("/cases/{case_id}/findings", response_model=FindingDetail, status_code=status.HTTP_201_CREATED)
async def create_finding(case_id: str, payload: FindingCreate, user: Analyst, db: DB) -> FindingDetail:
    case = await case_service.get_case(db, case_id)
    for eid in [*payload.supporting, *payload.contradicting]:
        ev = await ev_service.get_evidence(db, eid)
        if ev.case_id != case.id:
            from eyohe.core.errors import NotFoundError

            raise NotFoundError(f"Evidence {eid} is not on this case.")
    f = await f_service.create_finding(
        db,
        case.id,
        title=payload.title,
        claim=payload.claim,
        supporting=payload.supporting,
        contradicting=payload.contradicting,
        assessment=payload.assessment,
        category=payload.category,
        proposed_by="analyst",
        entity_ids=payload.entity_ids,
        severity=payload.severity,
        actor=user,
    )
    await case_service.refresh_counts(db, case.id)
    await db.commit()
    return await _detail(db, f.id)


async def _evidence_rows(db, ids: list[uuid.UUID]) -> list[dict[str, Any]]:  # type: ignore[no-untyped-def]
    if not ids:
        return []
    rows = (
        await db.execute(
            select(Evidence, Source).outerjoin(Source, Source.id == Evidence.source_id).where(Evidence.id.in_(ids))
        )
    ).all()
    out = []
    for ev, src in rows:
        d = EvidenceOut.model_validate(ev).model_dump(mode="json")
        d["source"] = (
            {
                "display_id": src.display_id,
                "url": src.url,
                "title": src.title,
                "tier": src.tier,
                "domain": src.domain,
                "collected_at": src.collected_at.isoformat(),
            }
            if src
            else None
        )
        out.append(d)
    return out


async def _detail(db, fid: uuid.UUID) -> FindingDetail:  # type: ignore[no-untyped-def]
    f = await f_service.get_finding(db, fid)
    links = await f_service.finding_evidence_links(db, f.id)
    sup = [e for e, r in links if r == "supports"]
    con = [e for e, r in links if r == "contradicts"]
    out = FindingDetail(**FindingOut.model_validate(f).model_dump())
    out.supporting = await _evidence_rows(db, sup)
    out.contradicting = await _evidence_rows(db, con)
    return out


@router.get("/findings/{finding_id}", response_model=FindingDetail)
async def get_finding(finding_id: str, _: CurrentUser, db: DB) -> FindingDetail:
    f = await f_service.get_finding(db, finding_id)
    return await _detail(db, f.id)


@router.get("/findings/{finding_id}/why", response_model=WhyOut)
async def why(finding_id: str, _: CurrentUser, db: DB) -> WhyOut:
    """Flagship 'Why?' view: finding → evidence chain → sources → computed confidence rationale."""
    f = await f_service.get_finding(db, finding_id)
    res = await f_service.compute_finding_confidence(db, f)
    links = await f_service.finding_evidence_links(db, f.id)
    rows = await _evidence_rows(db, [e for e, _ in links])
    roles = {str(e): r for e, r in links}
    chain = []
    for i, d in enumerate(rows, 1):
        chain.append(
            {
                "step": i,
                "evidence_id": d["display_id"],
                "role": roles.get(d["id"], "supports"),
                "claim": d["claim"],
                "excerpt": d["excerpt"],
                "excerpt_verified": d["excerpt_verified"],
                "evidence_type": d["evidence_type"],
                "collector": d["collector"],
                "collected_at": d["collected_at"],
                "review_state": d["review_state"],
                "source": d["source"],
            }
        )
    independent = len({(c["source"] or {}).get("domain") or c["collector"] for c in chain if c["role"] == "supports"})
    reasoning = " ".join(res.reasons) + (f" {independent} independent source(s) were considered." if chain else "")
    return WhyOut(finding=FindingOut.model_validate(f), confidence=res.to_dict(), chain=chain, reasoning=reasoning)


@router.post("/findings/{finding_id}/review", response_model=FindingDetail)
async def review_finding(finding_id: str, payload: dict[str, str], user: Analyst, db: DB) -> FindingDetail:
    from eyohe.core.errors import ValidationError

    f = await f_service.get_finding(db, finding_id)
    try:
        state = ReviewState(payload.get("state", ""))
    except ValueError as exc:
        raise ValidationError("state must be ACCEPTED, REJECTED, NEEDS_VERIFICATION or PENDING") from exc
    await f_service.review_finding(db, f, user, state, payload.get("note", ""))
    await db.commit()
    return await _detail(db, f.id)


@router.post("/findings/{finding_id}/evidence", response_model=FindingDetail)
async def attach(finding_id: str, payload: AttachEvidence, user: Analyst, db: DB) -> FindingDetail:
    f = await f_service.get_finding(db, finding_id)
    ev = await ev_service.get_evidence(db, payload.evidence_id)
    if ev.case_id != f.case_id:
        from eyohe.core.errors import NotFoundError

        raise NotFoundError("Evidence is not on this case.")
    await f_service.attach_evidence(db, f, ev.id, payload.role)
    await db.commit()
    return await _detail(db, f.id)


@router.get("/cases/{case_id}/timeline", response_model=list[TimelineOut])
async def timeline(case_id: str, _: CurrentUser, db: DB) -> list[TimelineOut]:
    case = await case_service.get_case(db, case_id)
    return [TimelineOut.model_validate(t) for t in await f_service.list_timeline(db, case.id)]
