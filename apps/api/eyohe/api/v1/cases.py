from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status

from eyohe.api.deps import DB, Analyst, CurrentUser
from eyohe.core.errors import NotFoundError
from eyohe.schemas.cases import (
    CaseCreate,
    CaseDetail,
    CaseOut,
    CaseUpdate,
    CloneRequest,
    NoteCreate,
    NoteOut,
    TargetCreate,
    TargetOut,
)
from eyohe.schemas.common import OkResponse, Page
from eyohe.services import cases as case_service

router = APIRouter(prefix="/cases", tags=["cases"])


@router.get("", response_model=Page[CaseOut])
async def list_cases(
    _: CurrentUser,
    db: DB,
    status_: str | None = Query(default=None, alias="status"),
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    include_archived: bool = False,
) -> Page[CaseOut]:
    items, total = await case_service.list_cases(
        db, status=status_, q=q, page=page, page_size=page_size, include_archived=include_archived
    )
    return Page(items=[CaseOut.model_validate(c) for c in items], total=total, page=page, page_size=page_size)


@router.post("", response_model=CaseDetail, status_code=status.HTTP_201_CREATED)
async def create_case(payload: CaseCreate, user: Analyst, db: DB) -> CaseDetail:
    case = await case_service.create_case(
        db,
        name=payload.name,
        actor=user,
        description=payload.description,
        objective=payload.objective,
        priority=payload.priority,
        tags=payload.tags,
        targets=payload.targets,
        classification=payload.classification,
    )
    await db.commit()
    return await _detail(db, case.id)


async def _detail(db, case_id: uuid.UUID) -> CaseDetail:  # type: ignore[no-untyped-def]
    case = await case_service.get_case(db, case_id)
    targets = await case_service.list_targets(db, case.id)
    return CaseDetail(
        **CaseOut.model_validate(case).model_dump(), targets=[TargetOut.model_validate(t) for t in targets]
    )


@router.get("/{case_id}", response_model=CaseDetail)
async def get_case(case_id: str, _: CurrentUser, db: DB) -> CaseDetail:
    case = await case_service.get_case(db, case_id)
    return await _detail(db, case.id)


@router.patch("/{case_id}", response_model=CaseDetail)
async def update_case(case_id: str, payload: CaseUpdate, user: Analyst, db: DB) -> CaseDetail:
    case = await case_service.get_case(db, case_id)
    await case_service.update_case(db, case, user, payload.model_dump(exclude_unset=True))
    await db.commit()
    return await _detail(db, case.id)


@router.delete("/{case_id}", response_model=OkResponse)
async def delete_case(case_id: str, user: Analyst, db: DB) -> OkResponse:
    case = await case_service.get_case(db, case_id)
    await case_service.delete_case(db, case, user)
    await db.commit()
    return OkResponse(message=f"Case {case.display_id} and its evidence vault were deleted.")


@router.post("/{case_id}/clone", response_model=CaseDetail, status_code=status.HTTP_201_CREATED)
async def clone_case(case_id: str, payload: CloneRequest, user: Analyst, db: DB) -> CaseDetail:
    case = await case_service.get_case(db, case_id)
    new = await case_service.clone_case(db, case, user, new_name=payload.name)
    await db.commit()
    return await _detail(db, new.id)


@router.get("/{case_id}/targets", response_model=list[TargetOut])
async def list_targets(case_id: str, _: CurrentUser, db: DB) -> list[TargetOut]:
    case = await case_service.get_case(db, case_id)
    return [TargetOut.model_validate(t) for t in await case_service.list_targets(db, case.id)]


@router.post("/{case_id}/targets", response_model=TargetOut, status_code=status.HTTP_201_CREATED)
async def add_target(case_id: str, payload: TargetCreate, user: Analyst, db: DB) -> TargetOut:
    case = await case_service.get_case(db, case_id)
    t = await case_service.add_target(
        db,
        case,
        payload.value,
        actor=user,
        label=payload.label,
        type_override=payload.type,
        is_primary=payload.is_primary,
        notes=payload.notes,
    )
    await db.commit()
    return TargetOut.model_validate(t)


@router.delete("/{case_id}/targets/{target_id}", response_model=OkResponse)
async def delete_target(case_id: str, target_id: uuid.UUID, user: Analyst, db: DB) -> OkResponse:
    case = await case_service.get_case(db, case_id)
    t = await case_service.get_target(db, target_id)
    if t.case_id != case.id:
        raise NotFoundError("Target not found on this case.")
    await db.delete(t)
    await db.commit()
    return OkResponse(message="Target removed.")


@router.get("/{case_id}/notes", response_model=list[NoteOut])
async def list_notes(case_id: str, _: CurrentUser, db: DB) -> list[NoteOut]:
    case = await case_service.get_case(db, case_id)
    return [NoteOut.model_validate(n) for n in await case_service.list_notes(db, case.id)]


@router.post("/{case_id}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
async def create_note(case_id: str, payload: NoteCreate, user: Analyst, db: DB) -> NoteOut:
    case = await case_service.get_case(db, case_id)
    n = await case_service.create_note(db, case, user, body=payload.body, title=payload.title, pinned=payload.pinned)
    await db.commit()
    return NoteOut.model_validate(n)


@router.delete("/{case_id}/notes/{note_id}", response_model=OkResponse)
async def delete_note(case_id: str, note_id: uuid.UUID, user: Analyst, db: DB) -> OkResponse:
    from eyohe.models.cases import Note

    case = await case_service.get_case(db, case_id)
    n = await db.get(Note, note_id)
    if n is None or n.case_id != case.id:
        raise NotFoundError("Note not found.")
    await db.delete(n)
    await db.commit()
    return OkResponse(message="Note deleted.")
