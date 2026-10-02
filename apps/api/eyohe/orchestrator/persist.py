"""Persist a collector's CollectResult with full provenance (sources → snapshots → evidence →
entities → relationships → timeline). Nothing is stored without a collector name and timestamp."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.collectors.base import CollectResult, EntityItem
from eyohe.core.enums import EventType
from eyohe.core.urlnorm import normalize_url
from eyohe.models.entities import Entity
from eyohe.models.evidence import Evidence
from eyohe.models.investigations import Investigation, InvestigationTask
from eyohe.models.sources import Source, SourceSnapshot
from eyohe.orchestrator.events import emit_event
from eyohe.services import entities as entity_service
from eyohe.services import evidence as evidence_service
from eyohe.services import findings as finding_service


@dataclass
class PersistStats:
    sources: int = 0
    new_sources: int = 0
    evidence: int = 0
    entities: int = 0
    new_entities: int = 0
    relationships: int = 0
    timeline: int = 0
    rejected: int = 0
    entity_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": self.sources,
            "new_sources": self.new_sources,
            "evidence": self.evidence,
            "entities": self.entities,
            "new_entities": self.new_entities,
            "relationships": self.relationships,
            "timeline": self.timeline,
            "rejected": self.rejected,
        }


async def persist_result(
    session: AsyncSession,
    inv: Investigation,
    task: InvestigationTask | None,
    result: CollectResult,
    *,
    emit: bool = True,
) -> PersistStats:
    stats = PersistStats()
    case_id = inv.case_id
    sources_by_url: dict[str, Source] = {}
    snapshots_by_url: dict[str, SourceSnapshot] = {}
    existing_entity_ids: set[uuid.UUID] = set()

    for s in result.sources:
        before = await _source_exists(session, case_id, s.url)
        src = await evidence_service.upsert_source(
            session,
            case_id,
            url=s.url,
            source_type=s.source_type,
            collector=result.collector,
            tier=s.tier,
            title=s.title,
            publisher=s.publisher,
            author=s.author,
            published_at=s.published_at,
            reliability_note=s.reliability_note,
            metadata=s.metadata,
        )
        stats.sources += 1
        if not before:
            stats.new_sources += 1
            if emit:
                await emit_event(
                    session,
                    inv,
                    EventType.SOURCE_DISCOVERED,
                    _stage(result.collector),
                    f"Source: {s.title or s.url}"[:300],
                    task_id=task.id if task else None,
                    data={"source_id": src.display_id, "url": src.canonical_url, "tier": src.tier},
                    commit=False,
                )
        sources_by_url[normalize_url(s.url)] = src
        if s.text_content or s.raw_content:
            snap = await evidence_service.add_snapshot(
                session,
                src,
                text_content=s.text_content,
                http_status=s.http_status,
                content_type=s.content_type,
                title=s.title,
                raw=s.raw_content,
                raw_mime=s.content_type.split(";")[0] or "text/html",
                metadata=s.metadata,
                final_url=s.final_url,
                fetch_ms=s.fetch_ms,
                truncated=s.truncated,
            )
            snapshots_by_url[normalize_url(s.url)] = snap

    evidence_by_key: dict[str, Evidence] = {}
    for item in result.evidence:
        ev_src = sources_by_url.get(normalize_url(item.source_url)) if item.source_url else None
        ev_snap = snapshots_by_url.get(normalize_url(item.source_url)) if item.source_url else None
        try:
            ev = await evidence_service.create_evidence(
                session,
                case_id,
                claim=item.claim,
                evidence_type=item.evidence_type,
                collector=result.collector,
                source=ev_src,
                snapshot=ev_snap,
                excerpt=item.excerpt,
                context=item.context,
                investigation_id=inv.id,
                observed_at=item.observed_at,
                structured=item.structured,
                collection_method=item.collection_method,
                require_excerpt_in_snapshot=bool(item.structured.get("require_excerpt_in_snapshot")),
            )
        except Exception as exc:
            stats.rejected += 1
            if emit:
                await emit_event(
                    session,
                    inv,
                    EventType.AI_CLAIM_REJECTED,
                    _stage(result.collector),
                    f"Evidence rejected: {exc}"[:300],
                    level="warning",
                    task_id=task.id if task else None,
                    commit=False,
                )
            continue
        stats.evidence += 1
        stats.evidence_ids.append(ev.display_id)
        if item.key:
            evidence_by_key[item.key] = ev
        ent_ids: list[uuid.UUID] = []
        for e in item.entities:
            ent = await _upsert(session, case_id, e, ev.id, existing_entity_ids, stats)
            ent_ids.append(ent.id)
        if ent_ids:
            await evidence_service.link_entities(session, ev, ent_ids)
        if emit:
            await emit_event(
                session,
                inv,
                EventType.EVIDENCE_CREATED,
                _stage(result.collector),
                f"{ev.display_id}: {ev.claim}"[:300],
                task_id=task.id if task else None,
                data={
                    "evidence_id": ev.display_id,
                    "type": ev.evidence_type,
                    "source": ev_src.display_id if ev_src else None,
                },
                commit=False,
            )

    for e in result.entities:
        await _upsert(session, case_id, e, None, existing_entity_ids, stats)

    for r in result.relationships:
        ev_ids = [evidence_by_key[k].id for k in r.evidence_keys if k in evidence_by_key]
        if not ev_ids:
            stats.rejected += 1
            continue
        src_e = await _upsert(session, case_id, r.source, None, existing_entity_ids, stats)
        dst_e = await _upsert(session, case_id, r.target, None, existing_entity_ids, stats)
        if src_e.id == dst_e.id:
            continue
        rel = await entity_service.create_relationship(
            session, case_id, src_e, dst_e, r.type, evidence_ids=ev_ids, rationale=r.rationale, attributes=r.attributes
        )
        stats.relationships += 1
        if emit:
            await emit_event(
                session,
                inv,
                EventType.RELATIONSHIP_CREATED,
                "GRAPH",
                f"{src_e.value} —{rel.type}→ {dst_e.value}"[:300],
                task_id=task.id if task else None,
                data={"relationship_id": rel.display_id, "confidence": rel.confidence},
                commit=False,
            )

    for t in result.timeline:
        tev = evidence_by_key.get(t.evidence_key)
        tl_entity_ids = [
            str((await _upsert(session, case_id, e, None, existing_entity_ids, stats)).id) for e in t.entities
        ]
        await finding_service.add_timeline_event(
            session,
            case_id,
            occurred_at=t.occurred_at,
            title=t.title,
            description=t.description,
            precision=t.precision,
            event_kind=t.event_kind,
            evidence_id=tev.id if tev else None,
            entity_ids=tl_entity_ids,
            confidence=tev.confidence if tev else "UNVERIFIED",
        )
        stats.timeline += 1

    if result.discovered_targets:
        disc = list(inv.stats.get("discovered_targets", []))
        for ttype, value in result.discovered_targets:
            entry = {"type": str(ttype), "value": value, "by": result.collector}
            if entry not in disc:
                disc.append(entry)
        inv.stats = {**inv.stats, "discovered_targets": disc[:200]}

    if stats.new_entities and emit:
        await emit_event(
            session,
            inv,
            EventType.ENTITY_DISCOVERED,
            _stage(result.collector),
            f"{stats.new_entities} new entities discovered",
            task_id=task.id if task else None,
            data={"entity_ids": stats.entity_ids[:50]},
            commit=False,
        )
    await session.flush()
    return stats


async def _source_exists(session: AsyncSession, case_id: uuid.UUID, url: str) -> bool:
    from sqlalchemy import select

    return (
        await session.execute(
            select(Source.id).where(Source.case_id == case_id, Source.canonical_url == normalize_url(url))
        )
    ).first() is not None


async def _upsert(
    session: AsyncSession,
    case_id: uuid.UUID,
    e: EntityItem,
    evidence_id: uuid.UUID | None,
    seen: set[uuid.UUID],
    stats: PersistStats,
) -> Entity:
    from sqlalchemy import select

    norm = entity_service.normalize_entity_value(e.type, e.value)
    existed = (
        await session.execute(
            select(Entity.id).where(
                Entity.case_id == case_id, Entity.type == str(e.type), Entity.normalized_value == norm
            )
        )
    ).first() is not None
    ent = await entity_service.upsert_entity(
        session, case_id, e.type, e.value, label=e.label, attributes=e.attributes, evidence_id=evidence_id
    )
    if ent.id not in seen:
        seen.add(ent.id)
        stats.entities += 1
        if not existed:
            stats.new_entities += 1
            stats.entity_ids.append(ent.display_id)
    return ent


def _stage(collector: str) -> str:
    return {
        "dns": "DNS",
        "rdap": "RDAP",
        "ct_logs": "CT",
        "github": "GITHUB",
        "reddit": "REDDIT",
        "wayback": "ARCHIVE",
        "web_fetch": "WEB",
        "search": "SEARCH",
        "news": "NEWS",
        "ip_info": "IP",
        "social_profiles": "SOCIAL",
        "documents": "DOCS",
        "research_agent": "AI",
    }.get(collector, collector.upper()[:12])
