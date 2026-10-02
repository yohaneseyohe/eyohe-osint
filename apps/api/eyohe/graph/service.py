"""Graph assembly from the relational store (default) or Neo4j (optional)."""

from __future__ import annotations

import uuid
from collections import defaultdict, deque

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.models.entities import Entity, Relationship, RelationshipEvidence
from eyohe.schemas.entities import GraphEdge, GraphNode, GraphOut


async def build_graph(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    focus: uuid.UUID | None = None,
    depth: int = 2,
    types: set[str] | None = None,
) -> GraphOut:
    ents = {
        e.id: e
        for e in (
            await session.execute(select(Entity).where(Entity.case_id == case_id, Entity.merged_into_id.is_(None)))
        ).scalars()
    }
    rels = list((await session.execute(select(Relationship).where(Relationship.case_id == case_id))).scalars())
    ev_counts: dict[uuid.UUID, int] = defaultdict(int)
    for (rid,) in (
        (
            await session.execute(
                select(RelationshipEvidence.relationship_id).where(
                    RelationshipEvidence.relationship_id.in_([r.id for r in rels])
                )
            )
        ).all()
        if rels
        else []
    ):
        ev_counts[rid] += 1
    if focus is not None and focus in ents:
        adj: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
        for r in rels:
            adj[r.source_entity_id].add(r.target_entity_id)
            adj[r.target_entity_id].add(r.source_entity_id)
        keep = {focus}
        q = deque([(focus, 0)])
        while q:
            n, d = q.popleft()
            if d >= depth:
                continue
            for m in adj[n]:
                if m not in keep:
                    keep.add(m)
                    q.append((m, d + 1))
        ents = {k: v for k, v in ents.items() if k in keep}
    if types:
        ents = {k: v for k, v in ents.items() if v.type in types or v.is_target}
    nodes = [
        GraphNode(
            id=str(e.id),
            display_id=e.display_id,
            type=e.type,
            label=e.label or e.value,
            value=e.value,
            confidence=e.confidence,
            is_target=e.is_target,
            evidence_count=len(e.evidence_ids or []),
            attributes={k: v for k, v in (e.attributes or {}).items() if k != "target"},
        )
        for e in ents.values()
    ]
    edges = [
        GraphEdge(
            id=str(r.id),
            display_id=r.display_id,
            source=str(r.source_entity_id),
            target=str(r.target_entity_id),
            type=r.type,
            confidence=r.confidence,
            review_state=r.review_state,
            evidence_count=ev_counts.get(r.id, 0),
            rationale=r.rationale,
        )
        for r in rels
        if r.source_entity_id in ents and r.target_entity_id in ents
    ]
    by_type: dict[str, int] = defaultdict(int)
    for node in nodes:
        by_type[node.type] += 1
    return GraphOut(
        nodes=nodes, edges=edges, stats={"nodes": len(nodes), "edges": len(edges), "by_type": dict(by_type)}
    )
