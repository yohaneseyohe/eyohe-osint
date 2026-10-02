"""Entities and evidence-backed relationships."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.db import utcnow
from eyohe.core.enums import AuditAction, Confidence, EntityType, RelationshipType, ReviewState
from eyohe.core.errors import NotFoundError, ValidationError
from eyohe.core.ids import next_display_id
from eyohe.core.urlnorm import normalize_url
from eyohe.models.auth import User
from eyohe.models.entities import Entity, EntityAlias, Relationship, RelationshipEvidence
from eyohe.models.evidence import Evidence
from eyohe.services.audit import record_audit


def normalize_entity_value(etype: EntityType, value: str) -> str:
    v = value.strip()
    if etype in (EntityType.DOMAIN, EntityType.EMAIL, EntityType.NAMESERVER, EntityType.MAIL_SERVER):
        return v.lower().rstrip(".")
    if etype == EntityType.USERNAME:
        return v.lstrip("@").lower()
    if etype == EntityType.SOCIAL_ACCOUNT:
        return v.lower()
    if etype == EntityType.URL:
        return normalize_url(v)
    if etype == EntityType.IP:
        return v.lower()
    if etype == EntityType.PHONE:
        return re.sub(r"[^0-9+]", "", v)
    if etype == EntityType.ASN:
        return "AS" + re.sub(r"(?i)^as", "", v).strip()
    if etype == EntityType.REPOSITORY:
        return v.lower().removesuffix(".git").strip("/")
    if etype in (
        EntityType.ORGANIZATION,
        EntityType.COMPANY,
        EntityType.PERSON,
        EntityType.LOCATION,
        EntityType.TECHNOLOGY,
    ):
        return re.sub(r"\s+", " ", v).strip().lower()
    return v


async def upsert_entity(
    session: AsyncSession,
    case_id: uuid.UUID,
    etype: EntityType,
    value: str,
    *,
    label: str = "",
    attributes: dict[str, Any] | None = None,
    evidence_id: uuid.UUID | None = None,
    is_target: bool = False,
    is_demo: bool = False,
) -> Entity:
    value = value.strip()
    if not value or len(value) > 2000:
        raise ValidationError("Entity value is empty or too long.")
    norm = normalize_entity_value(etype, value)
    ent = (
        await session.execute(
            select(Entity).where(Entity.case_id == case_id, Entity.type == str(etype), Entity.normalized_value == norm)
        )
    ).scalar_one_or_none()
    now = utcnow()
    if ent is None:
        ent = Entity(
            display_id=await next_display_id(session, "entity"),
            case_id=case_id,
            type=str(etype),
            value=value,
            normalized_value=norm,
            label=label or value,
            first_seen=now,
            last_seen=now,
            confidence=Confidence.UNVERIFIED,
            attributes=attributes or {},
            is_target=is_target,
            is_demo=is_demo,
            evidence_ids=[],
            source_count=0,
        )
        session.add(ent)
        await session.flush()
        await record_audit(
            session,
            AuditAction.ENTITY_CREATED,
            case_id=case_id,
            object_type="entity",
            object_id=ent.display_id,
            detail={"type": str(etype), "value": norm},
        )
    else:
        ent.last_seen = now
        if attributes:
            ent.attributes = {**ent.attributes, **attributes}
        if is_target:
            ent.is_target = True
        if label and not ent.label:
            ent.label = label
    if evidence_id is not None:
        ids = list(ent.evidence_ids or [])
        if str(evidence_id) not in ids:
            ids.append(str(evidence_id))
            ent.evidence_ids = ids
            ent.source_count = len(ids)
            ent.confidence = _entity_confidence(len(ids))
    return ent


def _entity_confidence(evidence_count: int) -> str:
    if evidence_count >= 3:
        return Confidence.CORROBORATED
    if evidence_count == 2:
        return Confidence.SUPPORTED
    if evidence_count == 1:
        return Confidence.POSSIBLE
    return Confidence.UNVERIFIED


async def add_alias(
    session: AsyncSession, entity: Entity, alias: str, alias_type: str = "name", evidence_id: uuid.UUID | None = None
) -> None:
    alias = alias.strip()
    if not alias or alias.lower() == entity.normalized_value:
        return
    exists = (
        await session.execute(
            select(EntityAlias.id).where(EntityAlias.entity_id == entity.id, EntityAlias.alias == alias)
        )
    ).first()
    if not exists:
        session.add(
            EntityAlias(
                entity_id=entity.id, alias=alias, alias_type=alias_type, evidence_id=evidence_id, created_at=utcnow()
            )
        )


async def get_entity(session: AsyncSession, entity_id: uuid.UUID | str) -> Entity:
    try:
        e = await session.get(Entity, uuid.UUID(str(entity_id)))
    except ValueError:
        e = (await session.execute(select(Entity).where(Entity.display_id == str(entity_id)))).scalar_one_or_none()
    if e is None:
        raise NotFoundError("Entity not found.")
    return e


async def list_entities(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    etype: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 100,
) -> tuple[list[Entity], int]:
    stmt = select(Entity).where(Entity.case_id == case_id, Entity.merged_into_id.is_(None))
    if etype:
        stmt = stmt.where(Entity.type == etype)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Entity.value.ilike(like), Entity.label.ilike(like), Entity.display_id.ilike(like)))
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(
            stmt.order_by(Entity.is_target.desc(), Entity.source_count.desc(), Entity.created_at)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars()
    return list(rows), total


async def create_relationship(
    session: AsyncSession,
    case_id: uuid.UUID,
    source: Entity,
    target: Entity,
    rtype: RelationshipType,
    *,
    evidence_ids: list[uuid.UUID],
    rationale: str = "",
    attributes: dict[str, Any] | None = None,
    is_demo: bool = False,
) -> Relationship:
    """Relationships require evidence. Identity claims (POSSIBLY_SAME_ENTITY) are never auto-confirmed."""
    if not evidence_ids:
        raise ValidationError("A relationship must be backed by at least one evidence record.")
    if source.id == target.id:
        raise ValidationError("An entity cannot relate to itself.")
    rel = (
        await session.execute(
            select(Relationship).where(
                Relationship.case_id == case_id,
                Relationship.source_entity_id == source.id,
                Relationship.target_entity_id == target.id,
                Relationship.type == str(rtype),
            )
        )
    ).scalar_one_or_none()
    if rel is None:
        rel = Relationship(
            display_id=await next_display_id(session, "relationship"),
            case_id=case_id,
            source_entity_id=source.id,
            target_entity_id=target.id,
            type=str(rtype),
            rationale=rationale,
            attributes=attributes or {},
            is_demo=is_demo,
            review_state=ReviewState.PENDING,
        )
        session.add(rel)
        await session.flush()
        await record_audit(
            session,
            AuditAction.RELATIONSHIP_CREATED,
            case_id=case_id,
            object_type="relationship",
            object_id=rel.display_id,
            detail={"type": str(rtype), "source": source.display_id, "target": target.display_id},
        )
    elif rationale and not rel.rationale:
        rel.rationale = rationale
    existing = {
        r.evidence_id
        for r in (
            await session.execute(select(RelationshipEvidence).where(RelationshipEvidence.relationship_id == rel.id))
        ).scalars()
    }
    for eid in evidence_ids:
        if eid not in existing:
            session.add(RelationshipEvidence(relationship_id=rel.id, evidence_id=eid, role="supports"))
            existing.add(eid)
    await session.flush()
    rel.confidence = await compute_relationship_confidence(session, rel)
    return rel


async def compute_relationship_confidence(session: AsyncSession, rel: Relationship) -> str:
    from eyohe.verification.confidence import assess

    links = list(
        (
            await session.execute(select(RelationshipEvidence).where(RelationshipEvidence.relationship_id == rel.id))
        ).scalars()
    )
    ev_ids = [link.evidence_id for link in links]
    evidence = (
        list((await session.execute(select(Evidence).where(Evidence.id.in_(ev_ids)))).scalars()) if ev_ids else []
    )
    roles = {link.evidence_id: link.role for link in links}
    result = assess(
        evidence, roles, identity_claim=rel.type == RelationshipType.POSSIBLY_SAME_ENTITY, review_state=rel.review_state
    )
    return result.label


async def review_relationship(
    session: AsyncSession, rel: Relationship, actor: User, state: ReviewState, note: str = ""
) -> Relationship:
    rel.review_state = str(state)
    rel.reviewed_by = actor.id
    rel.reviewed_at = utcnow()
    rel.review_note = note
    rel.confidence = await compute_relationship_confidence(session, rel)
    await record_audit(
        session,
        AuditAction.RELATIONSHIP_REVIEWED,
        actor_id=actor.id,
        actor_label=actor.username,
        case_id=rel.case_id,
        object_type="relationship",
        object_id=rel.display_id,
        detail={"state": str(state), "note": note},
    )
    return rel


async def list_relationships(
    session: AsyncSession, case_id: uuid.UUID, *, entity_id: uuid.UUID | None = None
) -> list[Relationship]:
    stmt = select(Relationship).where(Relationship.case_id == case_id)
    if entity_id:
        stmt = stmt.where(or_(Relationship.source_entity_id == entity_id, Relationship.target_entity_id == entity_id))
    return list((await session.execute(stmt.order_by(Relationship.created_at))).scalars())


async def relationship_evidence_ids(session: AsyncSession, rel_id: uuid.UUID) -> list[tuple[uuid.UUID, str]]:
    rows = await session.execute(
        select(RelationshipEvidence.evidence_id, RelationshipEvidence.role).where(
            RelationshipEvidence.relationship_id == rel_id
        )
    )
    return [(r[0], r[1]) for r in rows]
