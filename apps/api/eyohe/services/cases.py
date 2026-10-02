"""Case and target management."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.db import utcnow
from eyohe.core.enums import AuditAction, CaseStatus, EntityType, Priority, TargetType
from eyohe.core.errors import ConflictError, NotFoundError, ValidationError
from eyohe.core.ids import next_display_id
from eyohe.enrichment.classify import classify_target
from eyohe.models.auth import User
from eyohe.models.cases import Case, Note, Target
from eyohe.models.entities import Entity
from eyohe.services.audit import record_audit

_TARGET_TO_ENTITY = {
    TargetType.DOMAIN: EntityType.DOMAIN,
    TargetType.IP: EntityType.IP,
    TargetType.EMAIL: EntityType.EMAIL,
    TargetType.USERNAME: EntityType.USERNAME,
    TargetType.ORGANIZATION: EntityType.ORGANIZATION,
    TargetType.COMPANY: EntityType.COMPANY,
    TargetType.PERSON: EntityType.PERSON,
    TargetType.SOCIAL_ACCOUNT: EntityType.SOCIAL_ACCOUNT,
    TargetType.URL: EntityType.URL,
    TargetType.DOCUMENT: EntityType.DOCUMENT,
    TargetType.CRYPTO_ADDRESS: EntityType.CRYPTO_ADDRESS,
    TargetType.PHONE: EntityType.PHONE,
}


async def get_case(session: AsyncSession, case_id: uuid.UUID | str) -> Case:
    try:
        cid = uuid.UUID(str(case_id))
    except ValueError:
        row = (await session.execute(select(Case).where(Case.display_id == str(case_id)))).scalar_one_or_none()
        if row is None:
            raise NotFoundError(f"Case {case_id} not found.") from None
        return row
    case = await session.get(Case, cid)
    if case is None:
        raise NotFoundError(f"Case {case_id} not found.")
    return case


async def list_cases(
    session: AsyncSession,
    *,
    status: str | None = None,
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
    include_archived: bool = False,
) -> tuple[list[Case], int]:
    stmt = select(Case)
    if status:
        stmt = stmt.where(Case.status == status)
    elif not include_archived:
        stmt = stmt.where(Case.status != CaseStatus.ARCHIVED)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Case.name.ilike(like), Case.display_id.ilike(like), Case.description.ilike(like)))
    total = int((await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await session.execute(stmt.order_by(Case.updated_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).scalars()
    return list(rows), total


async def create_case(
    session: AsyncSession,
    *,
    name: str,
    actor: User | None,
    description: str = "",
    objective: str = "",
    priority: str = Priority.MEDIUM,
    tags: list[str] | None = None,
    targets: list[str] | None = None,
    classification: str = "RESEARCH",
    is_demo: bool = False,
) -> Case:
    if not name.strip():
        raise ValidationError("Case name is required.")
    case = Case(
        display_id=await next_display_id(session, "case"),
        name=name.strip()[:256],
        description=description,
        objective=objective,
        status=CaseStatus.DRAFT,
        priority=priority,
        tags=tags or [],
        analyst_id=actor.id if actor else None,
        classification=classification,
        is_demo=is_demo,
    )
    session.add(case)
    await session.flush()
    for i, t in enumerate(targets or []):
        await add_target(session, case, t, actor=actor, is_primary=(i == 0))
    await record_audit(
        session,
        AuditAction.CASE_CREATED,
        actor_id=actor.id if actor else None,
        actor_label=actor.username if actor else "system",
        case_id=case.id,
        object_type="case",
        object_id=case.display_id,
        detail={"name": case.name},
    )
    return case


async def update_case(session: AsyncSession, case: Case, actor: User, changes: dict[str, Any]) -> Case:
    allowed = {"name", "description", "objective", "status", "priority", "tags", "classification"}
    applied: dict[str, Any] = {}
    for k, v in changes.items():
        if k in allowed and v is not None:
            if k == "status":
                v = str(CaseStatus(v))
                if v in (CaseStatus.COMPLETED, CaseStatus.ARCHIVED) and case.closed_at is None:
                    case.closed_at = utcnow()
                if v == CaseStatus.ACTIVE:
                    case.closed_at = None
            setattr(case, k, v)
            applied[k] = v
    if applied:
        await record_audit(
            session,
            AuditAction.CASE_UPDATED,
            actor_id=actor.id,
            actor_label=actor.username,
            case_id=case.id,
            object_type="case",
            object_id=case.display_id,
            detail={"changes": applied},
        )
    return case


async def delete_case(session: AsyncSession, case: Case, actor: User) -> None:
    from eyohe.services.vault import get_vault

    get_vault().delete_case(case.id)
    await record_audit(
        session,
        AuditAction.CASE_DELETED,
        actor_id=actor.id,
        actor_label=actor.username,
        case_id=case.id,
        object_type="case",
        object_id=case.display_id,
        detail={"name": case.name},
    )
    await session.delete(case)


async def add_target(
    session: AsyncSession,
    case: Case,
    raw_value: str,
    *,
    actor: User | None,
    label: str = "",
    type_override: str | None = None,
    is_primary: bool = False,
    notes: str = "",
) -> Target:
    raw_value = raw_value.strip()
    if not raw_value:
        raise ValidationError("Target value is empty.")
    ttype, norm, extra = classify_target(raw_value)
    if type_override:
        ttype = TargetType(type_override)
    existing = (
        await session.execute(
            select(Target).where(Target.case_id == case.id, Target.type == str(ttype), Target.normalized_value == norm)
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictError(f"Target '{raw_value}' already exists on this case as {existing.type}.")
    # Each target is also an entity so it participates in the graph.
    from eyohe.services.entities import upsert_entity

    entity = await upsert_entity(
        session,
        case.id,
        _TARGET_TO_ENTITY.get(ttype, EntityType.ORGANIZATION),
        norm if ttype != TargetType.PERSON else raw_value,
        label=label or raw_value,
        attributes={**extra, "target": True},
        is_target=True,
    )
    target = Target(
        case_id=case.id,
        type=str(ttype),
        value=raw_value,
        normalized_value=norm,
        label=label,
        notes=notes,
        is_primary=is_primary,
        entity_id=entity.id,
        extra=extra,
    )
    session.add(target)
    await session.flush()
    await record_audit(
        session,
        AuditAction.TARGET_CREATED,
        actor_id=actor.id if actor else None,
        actor_label=actor.username if actor else "system",
        case_id=case.id,
        object_type="target",
        object_id=str(target.id),
        detail={"type": str(ttype), "value": norm},
    )
    return target


async def list_targets(session: AsyncSession, case_id: uuid.UUID) -> list[Target]:
    return list(
        (await session.execute(select(Target).where(Target.case_id == case_id).order_by(Target.created_at))).scalars()
    )


async def get_target(session: AsyncSession, target_id: uuid.UUID) -> Target:
    t = await session.get(Target, target_id)
    if t is None:
        raise NotFoundError("Target not found.")
    return t


async def refresh_counts(session: AsyncSession, case_id: uuid.UUID) -> None:
    from eyohe.models.evidence import Evidence
    from eyohe.models.findings import Finding
    from eyohe.models.sources import Source

    case = await session.get(Case, case_id)
    if case is None:
        return
    for attr, model in (
        ("evidence_count", Evidence),
        ("source_count", Source),
        ("entity_count", Entity),
        ("finding_count", Finding),
    ):
        n = (
            await session.execute(select(func.count()).select_from(model).where(model.case_id == case_id))
        ).scalar_one()
        setattr(case, attr, int(n))


async def clone_case(session: AsyncSession, case: Case, actor: User, *, new_name: str | None = None) -> Case:
    """Duplicate a case's definition (targets, objective, notes) without its collected data."""
    new = await create_case(
        session,
        name=new_name or f"{case.name} (copy)",
        actor=actor,
        description=case.description,
        objective=case.objective,
        priority=case.priority,
        tags=list(case.tags),
        classification=case.classification,
    )
    new.cloned_from_id = case.id
    for t in await list_targets(session, case.id):
        await add_target(
            session, new, t.value, actor=actor, label=t.label, type_override=t.type, is_primary=t.is_primary
        )
    for n in (await session.execute(select(Note).where(Note.case_id == case.id))).scalars():
        session.add(Note(case_id=new.id, author_id=n.author_id, title=n.title, body=n.body, pinned=n.pinned))
    await record_audit(
        session,
        AuditAction.CASE_CLONED,
        actor_id=actor.id,
        actor_label=actor.username,
        case_id=new.id,
        object_type="case",
        object_id=new.display_id,
        detail={"from": case.display_id},
    )
    return new


async def create_note(
    session: AsyncSession,
    case: Case,
    actor: User,
    *,
    body: str,
    title: str = "",
    pinned: bool = False,
) -> Note:
    import re

    if not body.strip():
        raise ValidationError("Note body is empty.")
    ev_refs = sorted(set(re.findall(r"EYO-EV-\d{6}", body)))
    ent_refs = sorted(set(re.findall(r"EYO-ENT-\d{6}", body)))
    note = Note(
        case_id=case.id,
        author_id=actor.id,
        title=title[:256],
        body=body,
        pinned=pinned,
        evidence_refs=ev_refs,
        entity_refs=ent_refs,
    )
    session.add(note)
    await session.flush()
    await record_audit(
        session,
        AuditAction.NOTE_CREATED,
        actor_id=actor.id,
        actor_label=actor.username,
        case_id=case.id,
        object_type="note",
        object_id=str(note.id),
    )
    return note


async def list_notes(session: AsyncSession, case_id: uuid.UUID) -> list[Note]:
    return list(
        (
            await session.execute(
                select(Note).where(Note.case_id == case_id).order_by(Note.pinned.desc(), Note.created_at.desc())
            )
        ).scalars()
    )
