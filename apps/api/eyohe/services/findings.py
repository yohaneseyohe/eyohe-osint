"""Findings (claims with computed confidence) and timeline events."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.db import utcnow
from eyohe.core.enums import AuditAction, ReviewState
from eyohe.core.errors import NotFoundError, ValidationError
from eyohe.core.ids import next_display_id
from eyohe.models.auth import User
from eyohe.models.evidence import Evidence
from eyohe.models.findings import Finding, FindingEvidence, TimelineEvent
from eyohe.models.sources import Source
from eyohe.services.audit import record_audit
from eyohe.verification.confidence import ConfidenceResult, assess


async def _evidence_context(
    session: AsyncSession, ev_ids: list[uuid.UUID]
) -> tuple[list[Evidence], dict[uuid.UUID, int], dict[uuid.UUID, str]]:
    if not ev_ids:
        return [], {}, {}
    evidence = list((await session.execute(select(Evidence).where(Evidence.id.in_(ev_ids)))).scalars())
    src_ids = [e.source_id for e in evidence if e.source_id]
    tiers: dict[uuid.UUID, int] = {}
    domains: dict[uuid.UUID, str] = {}
    if src_ids:
        for s in (await session.execute(select(Source).where(Source.id.in_(src_ids)))).scalars():
            tiers[s.id] = s.tier
            domains[s.id] = s.domain or s.canonical_url
    return evidence, tiers, domains


async def compute_finding_confidence(session: AsyncSession, finding: Finding) -> ConfidenceResult:
    links = list(
        (await session.execute(select(FindingEvidence).where(FindingEvidence.finding_id == finding.id))).scalars()
    )
    roles = {link.evidence_id: link.role for link in links}
    evidence, tiers, domains = await _evidence_context(session, list(roles))
    identity = finding.category in ("identity", "attribution")
    return assess(
        evidence,
        roles,
        identity_claim=identity,
        review_state=finding.review_state,
        source_tiers=tiers,
        source_domains=domains,
    )


async def create_finding(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    title: str,
    claim: str,
    supporting: list[uuid.UUID],
    contradicting: list[uuid.UUID] | None = None,
    assessment: str = "",
    category: str = "general",
    proposed_by: str = "system",
    investigation_id: uuid.UUID | None = None,
    entity_ids: list[str] | None = None,
    relationship_ids: list[str] | None = None,
    severity: str = "INFO",
    is_demo: bool = False,
    actor: User | None = None,
) -> Finding:
    if not title.strip() or not claim.strip():
        raise ValidationError("Finding title and claim are required.")
    if not supporting and not contradicting:
        raise ValidationError("A finding must reference at least one evidence record.")
    f = Finding(
        display_id=await next_display_id(session, "finding"),
        case_id=case_id,
        investigation_id=investigation_id,
        title=title.strip()[:512],
        claim=claim.strip(),
        assessment=assessment,
        category=category,
        proposed_by=proposed_by,
        entity_ids=entity_ids or [],
        relationship_ids=relationship_ids or [],
        severity=severity,
        is_demo=is_demo,
    )
    session.add(f)
    await session.flush()
    for eid in supporting:
        session.add(FindingEvidence(finding_id=f.id, evidence_id=eid, role="supports"))
    for eid in contradicting or []:
        session.add(FindingEvidence(finding_id=f.id, evidence_id=eid, role="contradicts"))
    await session.flush()
    res = await compute_finding_confidence(session, f)
    f.confidence = res.label
    f.confidence_rationale = res.to_dict()
    await record_audit(
        session,
        AuditAction.FINDING_CREATED,
        actor_id=actor.id if actor else None,
        actor_label=actor.username if actor else proposed_by,
        case_id=case_id,
        object_type="finding",
        object_id=f.display_id,
        detail={"title": f.title, "confidence": f.confidence},
    )
    return f


async def refresh_finding(session: AsyncSession, f: Finding) -> Finding:
    res = await compute_finding_confidence(session, f)
    f.confidence = res.label
    f.confidence_rationale = res.to_dict()
    return f


async def review_finding(session: AsyncSession, f: Finding, actor: User, state: ReviewState, note: str = "") -> Finding:
    f.review_state = str(state)
    f.reviewed_by = actor.id
    f.reviewed_at = utcnow()
    f.review_note = note[:4000]
    await refresh_finding(session, f)
    await record_audit(
        session,
        AuditAction.FINDING_REVIEWED,
        actor_id=actor.id,
        actor_label=actor.username,
        case_id=f.case_id,
        object_type="finding",
        object_id=f.display_id,
        detail={"state": str(state), "note": note[:500]},
    )
    return f


async def attach_evidence(session: AsyncSession, f: Finding, evidence_id: uuid.UUID, role: str = "supports") -> Finding:
    exists = (
        await session.execute(
            select(FindingEvidence).where(
                FindingEvidence.finding_id == f.id, FindingEvidence.evidence_id == evidence_id
            )
        )
    ).scalar_one_or_none()
    if exists:
        exists.role = role
    else:
        session.add(FindingEvidence(finding_id=f.id, evidence_id=evidence_id, role=role))
    await session.flush()
    return await refresh_finding(session, f)


async def get_finding(session: AsyncSession, finding_id: uuid.UUID | str) -> Finding:
    try:
        f = await session.get(Finding, uuid.UUID(str(finding_id)))
    except ValueError:
        f = (await session.execute(select(Finding).where(Finding.display_id == str(finding_id)))).scalar_one_or_none()
    if f is None:
        raise NotFoundError("Finding not found.")
    return f


async def list_findings(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    confidence: str | None = None,
    review_state: str | None = None,
    category: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[Finding], int]:
    stmt = select(Finding).where(Finding.case_id == case_id)
    if confidence:
        stmt = stmt.where(Finding.confidence == confidence)
    if review_state:
        stmt = stmt.where(Finding.review_state == review_state)
    if category:
        stmt = stmt.where(Finding.category == category)
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(stmt.order_by(Finding.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).scalars()
    return list(rows), total


async def finding_evidence_links(session: AsyncSession, finding_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
    rows = await session.execute(
        select(FindingEvidence.evidence_id, FindingEvidence.role).where(FindingEvidence.finding_id == finding_id)
    )
    return [(r[0], r[1]) for r in rows]


async def add_timeline_event(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    occurred_at: datetime,
    title: str,
    description: str = "",
    precision: str = "day",
    event_kind: str = "OBSERVATION",
    evidence_id: uuid.UUID | None = None,
    entity_ids: list[str] | None = None,
    confidence: str = "UNVERIFIED",
    is_demo: bool = False,
) -> TimelineEvent:
    # Deduplicate on (case, occurred_at, title).
    existing = (
        await session.execute(
            select(TimelineEvent).where(
                TimelineEvent.case_id == case_id,
                TimelineEvent.occurred_at == occurred_at,
                TimelineEvent.title == title[:512],
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    ev = TimelineEvent(
        case_id=case_id,
        occurred_at=occurred_at,
        precision=precision,
        title=title[:512],
        description=description,
        event_kind=event_kind,
        evidence_id=evidence_id,
        entity_ids=entity_ids or [],
        confidence=confidence,
        is_demo=is_demo,
    )
    session.add(ev)
    await session.flush()
    return ev


async def list_timeline(session: AsyncSession, case_id: uuid.UUID) -> list[TimelineEvent]:
    return list(
        (
            await session.execute(
                select(TimelineEvent).where(TimelineEvent.case_id == case_id).order_by(TimelineEvent.occurred_at)
            )
        ).scalars()
    )


def summarize_counts(items: list[Any], attr: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        k = getattr(it, attr)
        out[k] = out.get(k, 0) + 1
    return out
