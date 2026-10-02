from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query, status
from sqlalchemy import select

from eyohe.api.deps import DB, Analyst, CurrentUser
from eyohe.core.enums import EntityType, RelationshipType, ReviewState
from eyohe.core.errors import NotFoundError, ValidationError
from eyohe.models.entities import Relationship
from eyohe.models.evidence import Evidence
from eyohe.schemas.common import Page
from eyohe.schemas.entities import (
    EntityCreate,
    EntityOut,
    GraphOut,
    RelationshipCreate,
    RelationshipDetail,
    RelationshipOut,
)
from eyohe.schemas.evidence import EvidenceOut
from eyohe.services import cases as case_service
from eyohe.services import entities as ent_service
from eyohe.services import evidence as ev_service

router = APIRouter(tags=["entities"])


@router.get("/cases/{case_id}/entities", response_model=Page[EntityOut])
async def list_entities(
    case_id: str,
    _: CurrentUser,
    db: DB,
    type_: str | None = Query(default=None, alias="type"),
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=1000),
) -> Page[EntityOut]:
    case = await case_service.get_case(db, case_id)
    items, total = await ent_service.list_entities(db, case.id, etype=type_, q=q, page=page, page_size=page_size)
    return Page(items=[EntityOut.model_validate(e) for e in items], total=total, page=page, page_size=page_size)


@router.post("/cases/{case_id}/entities", response_model=EntityOut, status_code=status.HTTP_201_CREATED)
async def create_entity(case_id: str, payload: EntityCreate, user: Analyst, db: DB) -> EntityOut:
    case = await case_service.get_case(db, case_id)
    try:
        etype = EntityType(payload.type)
    except ValueError as exc:
        raise ValidationError(f"Unknown entity type {payload.type}") from exc
    ent = await ent_service.upsert_entity(
        db,
        case.id,
        etype,
        payload.value,
        label=payload.label,
        attributes={**payload.attributes, "created_by": user.username},
        evidence_id=payload.evidence_id,
    )
    await case_service.refresh_counts(db, case.id)
    await db.commit()
    return EntityOut.model_validate(ent)


@router.get("/entities/{entity_id}", response_model=dict[str, Any])
async def get_entity(entity_id: str, _: CurrentUser, db: DB) -> dict[str, Any]:
    ent = await ent_service.get_entity(db, entity_id)
    rels = await ent_service.list_relationships(db, ent.case_id, entity_id=ent.id)
    ev_ids = [uuid.UUID(x) for x in (ent.evidence_ids or [])]
    evidence = list((await db.execute(select(Evidence).where(Evidence.id.in_(ev_ids)))).scalars()) if ev_ids else []
    await db.refresh(ent, attribute_names=["aliases"])
    return {
        "entity": EntityOut.model_validate(ent).model_dump(mode="json"),
        "aliases": [{"alias": a.alias, "type": a.alias_type} for a in ent.aliases],
        "relationships": [RelationshipOut.model_validate(r).model_dump(mode="json") for r in rels],
        "evidence": [EvidenceOut.model_validate(e).model_dump(mode="json") for e in evidence],
    }


@router.get("/cases/{case_id}/relationships", response_model=list[RelationshipOut])
async def list_relationships(
    case_id: str, _: CurrentUser, db: DB, entity_id: uuid.UUID | None = None
) -> list[RelationshipOut]:
    case = await case_service.get_case(db, case_id)
    return [
        RelationshipOut.model_validate(r)
        for r in await ent_service.list_relationships(db, case.id, entity_id=entity_id)
    ]


@router.post("/cases/{case_id}/relationships", response_model=RelationshipDetail, status_code=status.HTTP_201_CREATED)
async def create_relationship(case_id: str, payload: RelationshipCreate, user: Analyst, db: DB) -> RelationshipDetail:
    case = await case_service.get_case(db, case_id)
    src = await ent_service.get_entity(db, payload.source_entity_id)
    dst = await ent_service.get_entity(db, payload.target_entity_id)
    if src.case_id != case.id or dst.case_id != case.id:
        raise NotFoundError("Entities must belong to this case.")
    try:
        rtype = RelationshipType(payload.type)
    except ValueError as exc:
        raise ValidationError(f"Unknown relationship type {payload.type}") from exc
    for eid in payload.evidence_ids:
        ev = await ev_service.get_evidence(db, eid)
        if ev.case_id != case.id:
            raise NotFoundError(f"Evidence {eid} not on this case.")
    rel = await ent_service.create_relationship(
        db,
        case.id,
        src,
        dst,
        rtype,
        evidence_ids=payload.evidence_ids,
        rationale=payload.rationale or f"Created by {user.username}",
    )
    await db.commit()
    return await _rel_detail(db, rel.id)


async def _rel_detail(db, rel_id: uuid.UUID) -> RelationshipDetail:  # type: ignore[no-untyped-def]
    rel = await db.get(Relationship, rel_id)
    if rel is None:
        raise NotFoundError("Relationship not found.")
    out = RelationshipDetail(**RelationshipOut.model_validate(rel).model_dump())
    links = await ent_service.relationship_evidence_ids(db, rel.id)
    ids = [e for e, _ in links]
    roles = dict(links)
    evidence = list((await db.execute(select(Evidence).where(Evidence.id.in_(ids)))).scalars()) if ids else []
    out.evidence = [
        {**EvidenceOut.model_validate(e).model_dump(mode="json"), "role": roles.get(e.id, "supports")} for e in evidence
    ]
    out.source_entity = EntityOut.model_validate(await ent_service.get_entity(db, rel.source_entity_id))
    out.target_entity = EntityOut.model_validate(await ent_service.get_entity(db, rel.target_entity_id))
    from eyohe.verification.confidence import assess

    res = assess(
        evidence, roles, identity_claim=rel.type == RelationshipType.POSSIBLY_SAME_ENTITY, review_state=rel.review_state
    )
    out.why = {
        "question": (
            f"Why does the relationship {out.source_entity.value} —{rel.type}→ {out.target_entity.value} exist?"
        ),
        "rationale": rel.rationale,
        "confidence": res.to_dict(),
        "chain": [
            {
                "evidence_id": e.display_id,
                "claim": e.claim,
                "source_url": (e.structured or {}).get("url"),
                "collector": e.collector,
                "collected_at": e.collected_at.isoformat(),
                "role": roles.get(e.id, "supports"),
            }
            for e in evidence
        ],
    }
    return out


@router.get("/relationships/{rel_id}", response_model=RelationshipDetail)
async def get_relationship(rel_id: uuid.UUID, _: CurrentUser, db: DB) -> RelationshipDetail:
    return await _rel_detail(db, rel_id)


@router.post("/relationships/{rel_id}/review", response_model=RelationshipDetail)
async def review_relationship(rel_id: uuid.UUID, payload: dict[str, str], user: Analyst, db: DB) -> RelationshipDetail:
    rel = await db.get(Relationship, rel_id)
    if rel is None:
        raise NotFoundError("Relationship not found.")
    try:
        state = ReviewState(payload.get("state", ""))
    except ValueError as exc:
        raise ValidationError("state must be ACCEPTED, REJECTED, NEEDS_VERIFICATION or PENDING") from exc
    await ent_service.review_relationship(db, rel, user, state, payload.get("note", ""))
    await db.commit()
    return await _rel_detail(db, rel.id)


@router.get("/cases/{case_id}/graph", response_model=GraphOut)
async def case_graph(
    case_id: str,
    _: CurrentUser,
    db: DB,
    entity_id: uuid.UUID | None = None,
    depth: int = Query(2, ge=1, le=4),
    types: str | None = None,
) -> GraphOut:
    from eyohe.graph.service import build_graph

    case = await case_service.get_case(db, case_id)
    type_filter = {t.strip().upper() for t in types.split(",")} if types else None
    return await build_graph(db, case.id, focus=entity_id, depth=depth, types=type_filter)


@router.post("/cases/{case_id}/graph/sync-neo4j")
async def sync_neo4j(case_id: str, _: Analyst, db: DB) -> dict[str, Any]:
    """Mirror the case graph into Neo4j (only when GRAPH_BACKEND=neo4j)."""
    from eyohe.core.config import get_settings
    from eyohe.core.errors import ConfigurationError

    if get_settings().graph_backend != "neo4j":
        raise ConfigurationError("GRAPH_BACKEND is postgresql; enable neo4j in .env to use this.")
    from eyohe.graph.neo4j_backend import Neo4jGraphBackend

    case = await case_service.get_case(db, case_id)
    backend = Neo4jGraphBackend()
    try:
        return await backend.sync_case(db, case.id)
    finally:
        await backend.close()
