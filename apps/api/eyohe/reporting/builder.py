"""Assemble the report model from the database. Every claim in the report is traceable: findings
carry their evidence IDs, evidence carries source IDs and URLs, and the evidence index lists them all."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe import __version__
from eyohe.core.config import get_settings
from eyohe.core.db import utcnow
from eyohe.models.auth import User
from eyohe.models.cases import Case, Note, Target
from eyohe.models.entities import Entity, Relationship, RelationshipEvidence
from eyohe.models.evidence import Evidence
from eyohe.models.findings import Finding, FindingEvidence, TimelineEvent
from eyohe.models.investigations import Investigation, InvestigationTask
from eyohe.models.sources import Source
from eyohe.verification.confidence import TIER_LABEL

CONFIDENCE_ORDER = ["CONFIRMED", "CORROBORATED", "SUPPORTED", "POSSIBLE", "INFERENCE", "UNVERIFIED", "CONTRADICTED"]
LANGUAGE_HINTS = {
    "TECHNICAL_RECORD": "FACT (technical record)",
    "DIRECT_STATEMENT": "PUBLIC STATEMENT (primary source)",
    "PUBLIC_STATEMENT": "PUBLIC STATEMENT (third party)",
    "ALLEGATION": "ALLEGATION",
    "SYSTEM_INTERPRETATION": "INFERENCE",
    "ARCHIVE_SNAPSHOT": "FACT (archived capture)",
    "DOCUMENT": "DOCUMENT",
    "SCREENSHOT": "SCREENSHOT",
}


@dataclass
class ReportData:
    case: Case
    analyst: str
    classification: str
    generated_at: datetime
    targets: list[Target]
    investigations: list[Investigation]
    tasks: dict[uuid.UUID, list[InvestigationTask]]
    findings: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    sources: list[Source]
    entities: list[Entity]
    relationships: list[dict[str, Any]]
    timeline: list[TimelineEvent]
    notes: list[Note]
    stats: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    version: str = __version__


async def build_report_data(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    analyst: User | None,
    classification: str | None = None,
    include_demo_label: bool = True,
) -> ReportData:
    case = await session.get(Case, case_id)
    if case is None:
        raise ValueError("case not found")
    targets = list(
        (
            await session.execute(select(Target).where(Target.case_id == case_id).order_by(Target.is_primary.desc()))
        ).scalars()
    )
    invs = list(
        (
            await session.execute(
                select(Investigation).where(Investigation.case_id == case_id).order_by(Investigation.created_at)
            )
        ).scalars()
    )
    tasks: dict[uuid.UUID, list[InvestigationTask]] = {}
    for inv in invs:
        await session.refresh(inv, attribute_names=["tasks"])
        tasks[inv.id] = sorted(inv.tasks, key=lambda t: t.order)
    sources = list(
        (
            await session.execute(
                select(Source).where(Source.case_id == case_id).order_by(Source.tier, Source.collected_at)
            )
        ).scalars()
    )
    src_by_id = {s.id: s for s in sources}
    ev_rows = list(
        (
            await session.execute(select(Evidence).where(Evidence.case_id == case_id).order_by(Evidence.display_id))
        ).scalars()
    )
    ev_by_id = {e.id: e for e in ev_rows}
    evidence = [
        {
            "id": e.display_id,
            "uuid": str(e.id),
            "type": e.evidence_type,
            "language": LANGUAGE_HINTS.get(e.evidence_type, e.evidence_type),
            "claim": e.claim,
            "excerpt": e.excerpt,
            "excerpt_verified": e.excerpt_verified,
            "confidence": e.confidence,
            "review_state": e.review_state,
            "collector": e.collector,
            "collected_at": e.collected_at,
            "observed_at": e.observed_at,
            "source": _src(src_by_id.get(e.source_id)) if e.source_id else None,
            "redacted": e.redacted,
        }
        for e in ev_rows
        if e.review_state != "REJECTED"
    ]
    findings_rows = list((await session.execute(select(Finding).where(Finding.case_id == case_id))).scalars())
    links: Any = (
        (
            await session.execute(
                select(FindingEvidence).where(FindingEvidence.finding_id.in_([f.id for f in findings_rows]))
            )
        ).scalars()
        if findings_rows
        else []
    )
    by_f: dict[uuid.UUID, list[tuple[Evidence, str]]] = {}
    for link in links:
        ev = ev_by_id.get(link.evidence_id)
        if ev:
            by_f.setdefault(link.finding_id, []).append((ev, link.role))
    findings = []
    for f in sorted(
        findings_rows,
        key=lambda x: (
            x.review_state == "REJECTED",
            CONFIDENCE_ORDER.index(x.confidence) if x.confidence in CONFIDENCE_ORDER else 9,
            x.created_at,
        ),
    ):
        if f.review_state == "REJECTED":
            continue
        sup = [ev for ev, r in by_f.get(f.id, []) if r == "supports"]
        con = [ev for ev, r in by_f.get(f.id, []) if r == "contradicts"]
        findings.append(
            {
                "id": f.display_id,
                "title": f.title,
                "claim": f.claim,
                "assessment": f.assessment,
                "category": f.category,
                "confidence": f.confidence,
                "rationale": f.confidence_rationale or {},
                "review_state": f.review_state,
                "proposed_by": f.proposed_by,
                "supporting": [
                    {
                        "id": e.display_id,
                        "claim": e.claim,
                        "source_url": (src_by_id[e.source_id].url if e.source_id in src_by_id else None),
                        "source_id": (src_by_id[e.source_id].display_id if e.source_id in src_by_id else None),
                        "type": e.evidence_type,
                    }
                    for e in sup
                ],
                "contradicting": [
                    {
                        "id": e.display_id,
                        "claim": e.claim,
                        "source_url": (src_by_id[e.source_id].url if e.source_id in src_by_id else None),
                        "source_id": (src_by_id[e.source_id].display_id if e.source_id in src_by_id else None),
                        "type": e.evidence_type,
                    }
                    for e in con
                ],
            }
        )
    entities = list(
        (
            await session.execute(
                select(Entity)
                .where(Entity.case_id == case_id, Entity.merged_into_id.is_(None))
                .order_by(Entity.is_target.desc(), Entity.type, Entity.source_count.desc())
            )
        ).scalars()
    )
    ent_by_id = {e.id: e for e in entities}
    rels = list(
        (
            await session.execute(
                select(Relationship).where(Relationship.case_id == case_id).order_by(Relationship.type)
            )
        ).scalars()
    )
    rel_ev: dict[uuid.UUID, list[str]] = {}
    for link in (
        (
            await session.execute(
                select(RelationshipEvidence).where(RelationshipEvidence.relationship_id.in_([r.id for r in rels]))
            )
        ).scalars()
        if rels
        else []
    ):
        rel_ev.setdefault(link.relationship_id, []).append(
            ev_by_id[link.evidence_id].display_id if link.evidence_id in ev_by_id else ""
        )
    relationships = [
        {
            "id": r.display_id,
            "source": ent_by_id[r.source_entity_id].value if r.source_entity_id in ent_by_id else "?",
            "target": ent_by_id[r.target_entity_id].value if r.target_entity_id in ent_by_id else "?",
            "source_type": ent_by_id[r.source_entity_id].type if r.source_entity_id in ent_by_id else "",
            "target_type": ent_by_id[r.target_entity_id].type if r.target_entity_id in ent_by_id else "",
            "type": r.type,
            "confidence": r.confidence,
            "review_state": r.review_state,
            "rationale": r.rationale,
            "evidence_ids": [x for x in rel_ev.get(r.id, []) if x],
        }
        for r in rels
        if r.review_state != "REJECTED"
    ]
    timeline = list(
        (
            await session.execute(
                select(TimelineEvent).where(TimelineEvent.case_id == case_id).order_by(TimelineEvent.occurred_at)
            )
        ).scalars()
    )
    notes = list(
        (
            await session.execute(
                select(Note).where(Note.case_id == case_id).order_by(Note.pinned.desc(), Note.created_at)
            )
        ).scalars()
    )
    s = get_settings()
    tiers: dict[int, int] = {}
    for src in sources:
        tiers[src.tier] = tiers.get(src.tier, 0) + 1
    stats = {
        "sources": len(sources),
        "evidence": len(evidence),
        "entities": len(entities),
        "relationships": len(relationships),
        "findings": len(findings),
        "timeline": len(timeline),
        "source_tiers": {TIER_LABEL[k]: v for k, v in sorted(tiers.items())},
        "confidence": {
            c: sum(1 for f in findings if f["confidence"] == c)
            for c in CONFIDENCE_ORDER
            if any(f["confidence"] == c for f in findings)
        },
        "collectors": sorted({src.collector for src in sources}),
        "verified_excerpts": sum(1 for e in evidence if e["excerpt_verified"]),
    }
    limitations = _limitations(invs, tasks, sources, evidence, findings)
    if case.is_demo and include_demo_label:
        limitations.insert(
            0,
            "DEMO DATA: this case contains fictional entities created to demonstrate the workstation. Nothing in it describes real people or organisations.",
        )
    return ReportData(
        case=case,
        analyst=(analyst.display_name or analyst.username) if analyst else "system",
        classification=classification or case.classification or s.report_classification,
        generated_at=utcnow(),
        targets=targets,
        investigations=invs,
        tasks=tasks,
        findings=findings,
        evidence=evidence,
        sources=sources,
        entities=entities,
        relationships=relationships,
        timeline=timeline,
        notes=notes,
        stats=stats,
        limitations=limitations,
    )


def _src(s: Source | None) -> dict[str, Any] | None:
    if s is None:
        return None
    return {
        "id": s.display_id,
        "url": s.url,
        "title": s.title,
        "domain": s.domain,
        "type": s.source_type,
        "tier": s.tier,
        "tier_label": TIER_LABEL.get(s.tier, ""),
        "publisher": s.publisher,
        "author": s.author,
        "published_at": s.published_at,
        "collected_at": s.collected_at,
        "collector": s.collector,
    }


def _limitations(
    invs: list[Investigation],
    tasks: dict[uuid.UUID, list[InvestigationTask]],
    sources: list[Source],
    evidence: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> list[str]:
    out = [
        "All information was collected from publicly accessible sources only; no authentication, paywall or anti-bot controls were bypassed."
    ]
    skipped = [t for ts in tasks.values() for t in ts if t.status in ("SKIPPED", "FAILED", "DISABLED")]
    if skipped:
        names = sorted({f"{t.title} ({t.status.lower()}{': ' + t.error[:80] if t.error else ''})" for t in skipped})
        out.append(
            "Some planned collection tasks did not complete: "
            + "; ".join(names[:8])
            + (" …" if len(names) > 8 else "")
            + ". Coverage of those areas is incomplete."
        )
    low = sum(1 for s in sources if s.tier >= 4)
    if sources and low / len(sources) > 0.5:
        out.append(
            f"{low} of {len(sources)} sources are community or unassessed sources (tier 4-5); statements from them are reported as public statements or allegations, not facts."
        )
    unverified = [f for f in findings if f["confidence"] in ("UNVERIFIED", "POSSIBLE", "INFERENCE")]
    if unverified:
        out.append(
            f"{len(unverified)} finding(s) rest on a single source or inference and could not be independently verified."
        )
    contradicted = [f for f in findings if f["confidence"] == "CONTRADICTED"]
    if contradicted:
        out.append(
            f"{len(contradicted)} finding(s) are contradicted by other evidence and are presented as CONFLICTING SOURCES."
        )
    identity = [f for f in findings if f["category"] in ("identity", "attribution") and f["review_state"] != "ACCEPTED"]
    if identity:
        out.append(
            "Identity/attribution findings are possibilities proposed from public indicators; they were not confirmed by the analyst and must not be treated as established."
        )
    if not evidence:
        out.append("No evidence has been collected for this case yet.")
    out.append(
        "Live technical records (DNS, certificates, archives) reflect the state at collection time and may have changed since."
    )
    return out
