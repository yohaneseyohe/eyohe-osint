"""Sources, snapshots and evidence records with full provenance."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.db import utcnow
from eyohe.core.enums import AuditAction, Confidence, EvidenceType, ReviewState, SourceType
from eyohe.core.errors import NotFoundError, ValidationError
from eyohe.core.ids import next_display_id
from eyohe.core.logging import contains_secret, redact_text
from eyohe.core.metrics import evidence_created, sources_collected
from eyohe.core.security import sha256_text
from eyohe.core.urlnorm import normalize_url, registrable_domain
from eyohe.models.auth import User
from eyohe.models.evidence import Evidence, EvidenceArtifact
from eyohe.models.sources import Source, SourceSnapshot
from eyohe.services.audit import record_audit
from eyohe.services.vault import get_vault

_WS = re.compile(r"\s+")


def _norm_ws(s: str) -> str:
    return _WS.sub(" ", s).strip().lower()


def excerpt_in_text(excerpt: str, text: str) -> bool:
    """Whitespace/case-insensitive substring check used as the quote hallucination guard."""
    if not excerpt or not text:
        return False
    return _norm_ws(excerpt) in _norm_ws(text)


async def upsert_source(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    url: str,
    source_type: SourceType,
    collector: str,
    tier: int,
    title: str = "",
    publisher: str = "",
    author: str = "",
    published_at: datetime | None = None,
    reliability_note: str = "",
    metadata: dict[str, Any] | None = None,
    is_demo: bool = False,
) -> Source:
    canonical = normalize_url(url)
    src = (
        await session.execute(select(Source).where(Source.case_id == case_id, Source.canonical_url == canonical))
    ).scalar_one_or_none()
    if src is None:
        src = Source(
            display_id=await next_display_id(session, "source"),
            case_id=case_id,
            source_type=str(source_type),
            url=url,
            canonical_url=canonical,
            domain=registrable_domain(url),
            title=title[:2000],
            publisher=publisher[:256],
            author=author[:256],
            published_at=published_at,
            collected_at=utcnow(),
            collector=collector,
            tier=tier,
            reliability_note=reliability_note,
            metadata_=metadata or {},
            is_demo=is_demo,
        )
        session.add(src)
        await session.flush()
        sources_collected.labels(collector=collector).inc()
        await record_audit(
            session,
            AuditAction.SOURCE_DISCOVERED,
            case_id=case_id,
            object_type="source",
            object_id=src.display_id,
            detail={"url": canonical, "collector": collector},
        )
    else:
        if title and not src.title:
            src.title = title[:2000]
        if published_at and not src.published_at:
            src.published_at = published_at
        if metadata:
            src.metadata_ = {**src.metadata_, **metadata}
        if tier < src.tier:
            src.tier = tier
    return src


async def add_snapshot(
    session: AsyncSession,
    source: Source,
    *,
    text_content: str,
    http_status: int | None = None,
    content_type: str = "",
    title: str = "",
    raw: bytes | None = None,
    raw_mime: str = "text/html",
    metadata: dict[str, Any] | None = None,
    final_url: str | None = None,
    fetch_ms: int | None = None,
    truncated: bool = False,
) -> SourceSnapshot:
    from eyohe.core.config import get_settings

    limit = get_settings().snapshot_max_text_chars
    text_content = redact_text(text_content)
    if len(text_content) > limit:
        text_content = text_content[:limit]
        truncated = True
    content_hash = sha256_text(text_content)
    latest = (
        await session.execute(
            select(SourceSnapshot)
            .where(SourceSnapshot.source_id == source.id)
            .order_by(SourceSnapshot.retrieved_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    artifact_path = None
    if raw:
        if contains_secret(raw.decode("utf-8", errors="ignore")):
            raw = redact_text(raw.decode("utf-8", errors="ignore")).encode()
        desc = get_vault().store(
            source.case_id,
            raw,
            raw_mime,
            kind="snapshot",
            original_url=source.url,
            metadata={"source_id": str(source.id)},
        )
        artifact_path = desc["path"]
    snap = SourceSnapshot(
        source_id=source.id,
        case_id=source.case_id,
        retrieved_at=utcnow(),
        http_status=http_status,
        content_type=content_type[:128],
        title=title[:2000],
        content_hash=content_hash,
        text_content=text_content,
        text_chars=len(text_content),
        artifact_path=artifact_path,
        metadata_=metadata or {},
        final_url=final_url,
        fetch_ms=fetch_ms,
        truncated=truncated,
    )
    if latest and latest.content_hash == content_hash:
        snap.metadata_ = {**snap.metadata_, "unchanged_since": latest.retrieved_at.isoformat()}
    session.add(snap)
    await session.flush()
    return snap


async def create_evidence(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    claim: str,
    evidence_type: EvidenceType,
    collector: str,
    source: Source | None = None,
    snapshot: SourceSnapshot | None = None,
    excerpt: str = "",
    context: str = "",
    investigation_id: uuid.UUID | None = None,
    observed_at: datetime | None = None,
    structured: dict[str, Any] | None = None,
    collection_method: str = "",
    require_excerpt_in_snapshot: bool = False,
    is_demo: bool = False,
    artifacts: list[tuple[bytes, str, str]] | None = None,
) -> Evidence:
    """Create an evidence record. If ``require_excerpt_in_snapshot`` the excerpt must be found in
    the snapshot text (used for LLM-extracted claims) or a ValidationError is raised."""
    claim = claim.strip()
    if not claim:
        raise ValidationError("Evidence claim is empty.")
    excerpt = redact_text(excerpt.strip())[:4000]
    verified = False
    if snapshot is not None and excerpt:
        verified = excerpt_in_text(excerpt, snapshot.text_content)
        if require_excerpt_in_snapshot and not verified:
            raise ValidationError(
                "Excerpt was not found in the collected source text; evidence rejected (possible hallucination)."
            )
    structured = dict(structured or {})
    if source is not None:
        structured.setdefault("url", source.url)
        structured.setdefault("tier", source.tier)
        structured.setdefault("source_display_id", source.display_id)
    redacted = contains_secret(claim) or contains_secret(excerpt)
    ev = Evidence(
        display_id=await next_display_id(session, "evidence"),
        case_id=case_id,
        investigation_id=investigation_id,
        source_id=source.id if source else None,
        snapshot_id=snapshot.id if snapshot else None,
        evidence_type=str(evidence_type),
        claim=redact_text(claim)[:4000],
        excerpt=excerpt,
        excerpt_verified=verified,
        context=redact_text(context)[:4000],
        collector=collector,
        collection_method=collection_method,
        collected_at=utcnow(),
        observed_at=observed_at,
        confidence=_initial_confidence(evidence_type, source),
        review_state=ReviewState.PENDING,
        content_hash=sha256_text(f"{claim}|{excerpt}|{source.canonical_url if source else ''}"),
        structured=structured,
        entity_ids=[],
        is_demo=is_demo,
        redacted=redacted,
    )
    session.add(ev)
    await session.flush()
    for content, mime, kind in artifacts or []:
        desc = get_vault().store(case_id, content, mime, kind=kind, original_url=source.url if source else None)
        session.add(
            EvidenceArtifact(
                evidence_id=ev.id,
                case_id=case_id,
                source_id=source.id if source else None,
                kind=kind,
                path=desc["path"],
                mime_type=mime,
                sha256=desc["sha256"],
                size_bytes=desc["size_bytes"],
                original_url=desc["original_url"],
                created_at=utcnow(),
                metadata_={},
            )
        )
    evidence_created.labels(collector=collector).inc()
    await record_audit(
        session,
        AuditAction.EVIDENCE_CREATED,
        case_id=case_id,
        object_type="evidence",
        object_id=ev.display_id,
        detail={"type": str(evidence_type), "collector": collector, "source": source.display_id if source else None},
    )
    return ev


def _initial_confidence(evidence_type: EvidenceType, source: Source | None) -> str:
    if evidence_type == EvidenceType.SYSTEM_INTERPRETATION:
        return Confidence.INFERENCE
    if evidence_type == EvidenceType.ALLEGATION:
        return Confidence.UNVERIFIED
    if source is not None and source.tier <= 2:
        return Confidence.SUPPORTED
    if evidence_type == EvidenceType.TECHNICAL_RECORD and source is not None and source.tier <= 3:
        return Confidence.SUPPORTED
    return Confidence.POSSIBLE


async def get_evidence(session: AsyncSession, evidence_id: uuid.UUID | str) -> Evidence:
    try:
        e = await session.get(Evidence, uuid.UUID(str(evidence_id)))
    except ValueError:
        e = (
            await session.execute(select(Evidence).where(Evidence.display_id == str(evidence_id)))
        ).scalar_one_or_none()
    if e is None:
        raise NotFoundError(f"Evidence {evidence_id} not found.")
    return e


async def list_evidence(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    evidence_type: str | None = None,
    review_state: str | None = None,
    confidence: str | None = None,
    source_id: uuid.UUID | None = None,
    q: str | None = None,
    collector: str | None = None,
    entity_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Evidence], int]:
    stmt = select(Evidence).where(Evidence.case_id == case_id)
    if evidence_type:
        stmt = stmt.where(Evidence.evidence_type == evidence_type)
    if review_state:
        stmt = stmt.where(Evidence.review_state == review_state)
    if confidence:
        stmt = stmt.where(Evidence.confidence == confidence)
    if source_id:
        stmt = stmt.where(Evidence.source_id == source_id)
    if collector:
        stmt = stmt.where(Evidence.collector == collector)
    if entity_id:
        stmt = stmt.where(Evidence.entity_ids.cast(__import__("sqlalchemy").Text).ilike(f"%{entity_id}%"))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(Evidence.claim.ilike(like), Evidence.excerpt.ilike(like), Evidence.display_id.ilike(like))
        )
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(stmt.order_by(Evidence.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).scalars()
    return list(rows), total


async def review_evidence(
    session: AsyncSession, ev: Evidence, actor: User, state: ReviewState, note: str = ""
) -> Evidence:
    ev.review_state = str(state)
    ev.reviewed_by = actor.id
    ev.reviewed_at = utcnow()
    ev.review_note = note[:4000]
    if state == ReviewState.REJECTED:
        ev.confidence = Confidence.CONTRADICTED
    elif state == ReviewState.NEEDS_VERIFICATION:
        ev.confidence = Confidence.UNVERIFIED
    elif state == ReviewState.ACCEPTED and ev.confidence in (Confidence.UNVERIFIED, Confidence.CONTRADICTED):
        ev.confidence = Confidence.POSSIBLE
    await record_audit(
        session,
        AuditAction.EVIDENCE_REVIEWED,
        actor_id=actor.id,
        actor_label=actor.username,
        case_id=ev.case_id,
        object_type="evidence",
        object_id=ev.display_id,
        detail={"state": str(state), "note": note[:500]},
    )
    return ev


async def link_entities(session: AsyncSession, ev: Evidence, entity_ids: list[uuid.UUID]) -> None:
    ids = list(ev.entity_ids or [])
    for eid in entity_ids:
        if str(eid) not in ids:
            ids.append(str(eid))
    ev.entity_ids = ids


async def list_sources(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    source_type: str | None = None,
    collector: str | None = None,
    max_tier: int | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Source], int]:
    stmt = select(Source).where(Source.case_id == case_id)
    if source_type:
        stmt = stmt.where(Source.source_type == source_type)
    if collector:
        stmt = stmt.where(Source.collector == collector)
    if max_tier:
        stmt = stmt.where(Source.tier <= max_tier)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Source.url.ilike(like), Source.title.ilike(like), Source.domain.ilike(like)))
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(stmt.order_by(Source.collected_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).scalars()
    return list(rows), total


async def get_source(session: AsyncSession, source_id: uuid.UUID | str) -> Source:
    try:
        s = await session.get(Source, uuid.UUID(str(source_id)))
    except ValueError:
        s = (await session.execute(select(Source).where(Source.display_id == str(source_id)))).scalar_one_or_none()
    if s is None:
        raise NotFoundError("Source not found.")
    return s


async def latest_snapshot(session: AsyncSession, source_id: uuid.UUID) -> SourceSnapshot | None:
    return (
        await session.execute(
            select(SourceSnapshot)
            .where(SourceSnapshot.source_id == source_id)
            .order_by(SourceSnapshot.retrieved_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
