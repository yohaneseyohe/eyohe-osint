from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Any

import orjson
from fastapi import APIRouter, Query, Request, status
from sse_starlette.sse import EventSourceResponse

from eyohe.api.deps import DB, Analyst, CurrentUser
from eyohe.core.enums import InvestigationStatus
from eyohe.core.errors import NotFoundError
from eyohe.orchestrator.events import event_bus, replay_events
from eyohe.orchestrator.planner import TASK_CATALOGUE
from eyohe.schemas.common import OkResponse
from eyohe.schemas.investigations import (
    ControlRequest,
    CustomTask,
    EventOut,
    InvestigationDetail,
    InvestigationOut,
    InvestigationStart,
    PlanUpdate,
    TaskOut,
)
from eyohe.services import cases as case_service
from eyohe.services import investigations as inv_service

router = APIRouter(prefix="/investigations", tags=["investigations"])


async def _detail(db, inv_id: uuid.UUID) -> InvestigationDetail:  # type: ignore[no-untyped-def]
    inv = await inv_service.get_investigation(db, inv_id)
    await db.refresh(inv, attribute_names=["tasks"])
    return InvestigationDetail(
        **InvestigationOut.model_validate(inv).model_dump(),
        tasks=[TaskOut.model_validate(t) for t in sorted(inv.tasks, key=lambda t: t.order)],
    )


@router.get("", response_model=list[InvestigationOut])
async def list_investigations(
    _: CurrentUser, db: DB, case_id: uuid.UUID | None = None, status_: str | None = Query(default=None, alias="status")
) -> list[InvestigationOut]:
    return [
        InvestigationOut.model_validate(i) for i in await inv_service.list_investigations(db, case_id, status=status_)
    ]


@router.get("/task-catalogue")
async def task_catalogue(_: CurrentUser) -> dict[str, Any]:
    return TASK_CATALOGUE


@router.post("/start", response_model=InvestigationDetail, status_code=status.HTTP_201_CREATED)
async def start_investigation(payload: InvestigationStart, user: Analyst, db: DB) -> InvestigationDetail:
    """Create an investigation, generate its plan, and (optionally) approve + run immediately."""
    case = await case_service.get_case(db, payload.case_id)
    target = None
    if payload.target_id:
        target = await case_service.get_target(db, payload.target_id)
        if target.case_id != case.id:
            raise NotFoundError("Target not found on this case.")
    inv = await inv_service.create_investigation(
        db, case, user, request_text=payload.request_text, target=target, name=payload.name, bounds=payload.bounds
    )
    await db.commit()
    await inv_service.plan_investigation(db, inv, user, use_ai=payload.use_ai)
    await db.commit()
    if payload.auto_approve:
        await inv_service.approve_and_start(db, inv, user)
    return await _detail(db, inv.id)


@router.get("/{inv_id}", response_model=InvestigationDetail)
async def get_investigation(inv_id: str, _: CurrentUser, db: DB) -> InvestigationDetail:
    inv = await inv_service.get_investigation(db, inv_id)
    return await _detail(db, inv.id)


@router.get("/{inv_id}/status")
async def investigation_status(inv_id: str, _: CurrentUser, db: DB) -> dict[str, Any]:
    inv = await inv_service.get_investigation(db, inv_id)
    await db.refresh(inv, attribute_names=["tasks"])
    return await inv_service.status_summary(db, inv)


@router.post("/{inv_id}/plan", response_model=InvestigationDetail)
async def replan(inv_id: str, user: Analyst, db: DB, use_ai: bool = True) -> InvestigationDetail:
    inv = await inv_service.get_investigation(db, inv_id)
    if inv.status not in (InvestigationStatus.DRAFT, InvestigationStatus.AWAITING_APPROVAL, InvestigationStatus.FAILED):
        inv.status = InvestigationStatus.DRAFT
    elif inv.status == InvestigationStatus.AWAITING_APPROVAL:
        inv.status = InvestigationStatus.DRAFT
    await db.commit()
    await inv_service.plan_investigation(db, inv, user, use_ai=use_ai)
    await db.commit()
    return await _detail(db, inv.id)


@router.patch("/{inv_id}/plan", response_model=InvestigationDetail)
async def update_plan(inv_id: str, payload: PlanUpdate, user: Analyst, db: DB) -> InvestigationDetail:
    inv = await inv_service.get_investigation(db, inv_id)
    await db.refresh(inv, attribute_names=["tasks"])
    await inv_service.update_plan_tasks(db, inv, user, [c.model_dump() for c in payload.tasks])
    await db.commit()
    return await _detail(db, inv.id)


@router.post("/{inv_id}/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
async def add_task(inv_id: str, payload: CustomTask, user: Analyst, db: DB) -> TaskOut:
    inv = await inv_service.get_investigation(db, inv_id)
    await db.refresh(inv, attribute_names=["tasks"])
    task = await inv_service.add_custom_task(db, inv, user, payload.task_type, payload.params, payload.rationale)
    await db.commit()
    return TaskOut.model_validate(task)


@router.post("/{inv_id}/approve", response_model=InvestigationDetail)
async def approve(inv_id: str, user: Analyst, db: DB) -> InvestigationDetail:
    inv = await inv_service.get_investigation(db, inv_id)
    await inv_service.approve_and_start(db, inv, user)
    return await _detail(db, inv.id)


@router.post("/{inv_id}/control", response_model=InvestigationDetail)
async def control(inv_id: str, payload: ControlRequest, user: Analyst, db: DB) -> InvestigationDetail:
    inv = await inv_service.get_investigation(db, inv_id)
    await inv_service.request_control(db, inv, user, payload.action)
    return await _detail(db, inv.id)


@router.get("/{inv_id}/events", response_model=list[EventOut])
async def list_events(
    inv_id: str, _: CurrentUser, db: DB, after: int = 0, limit: int = Query(500, le=2000)
) -> list[EventOut]:
    inv = await inv_service.get_investigation(db, inv_id)
    return [EventOut(**e) for e in await replay_events(inv.id, after, limit)]


@router.get("/{inv_id}/events/stream")
async def stream_events(inv_id: str, request: Request, _: CurrentUser, db: DB, after: int = 0) -> EventSourceResponse:
    """Server-Sent Events: replays persisted events after ``after`` then follows live events."""
    inv = await inv_service.get_investigation(db, inv_id)
    inv_key = str(inv.id)

    async def gen() -> AsyncIterator[dict[str, Any]]:
        last = after
        for e in await replay_events(inv.id, after, 2000):
            last = e["seq"]
            yield {"event": "investigation", "id": str(last), "data": orjson.dumps(e).decode()}
        sub = event_bus.subscribe(inv_key).__aiter__()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    e = await asyncio.wait_for(sub.__anext__(), timeout=15)
                except TimeoutError:
                    yield {"event": "ping", "data": orjson.dumps({"seq": last}).decode()}
                    continue
                if e["seq"] <= last:
                    continue
                if e["seq"] > last + 1:  # gap (e.g. produced by a worker) → fill from DB
                    for missed in await replay_events(inv.id, last, 2000):
                        last = missed["seq"]
                        yield {"event": "investigation", "id": str(last), "data": orjson.dumps(missed).decode()}
                    continue
                last = e["seq"]
                yield {"event": "investigation", "id": str(last), "data": orjson.dumps(e).decode()}
        finally:
            aclose = getattr(sub, "aclose", None)
            if aclose is not None:
                await aclose()

    return EventSourceResponse(gen(), ping=20)


@router.delete("/{inv_id}", response_model=OkResponse)
async def delete_investigation(inv_id: str, user: Analyst, db: DB) -> OkResponse:
    inv = await inv_service.get_investigation(db, inv_id)
    if inv.status in (InvestigationStatus.RUNNING, InvestigationStatus.VERIFYING):
        from eyohe.core.errors import ConflictError

        raise ConflictError("Stop the investigation before deleting it.")
    await db.delete(inv)
    await db.commit()
    return OkResponse(message="Investigation deleted (collected evidence remains on the case).")
