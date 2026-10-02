from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from eyohe.api.deps import DB, Analyst, CurrentUser
from eyohe.core.db import utcnow
from eyohe.core.errors import NotFoundError
from eyohe.models.monitoring import Alert, Monitor
from eyohe.scheduler import monitors as mon_service
from eyohe.services import cases as case_service

router = APIRouter(tags=["monitoring"])


class MonitorCreate(BaseModel):
    case_id: uuid.UUID
    name: str = Field(min_length=1, max_length=256)
    target_id: uuid.UUID | None = None
    target_value: str | None = None
    target_type: str | None = None
    checks: list[str] = Field(default_factory=lambda: ["dns", "search"])
    schedule: str = "daily"
    keywords: list[str] = Field(default_factory=list)
    notify: dict[str, Any] = Field(default_factory=dict)


class MonitorUpdate(BaseModel):
    name: str | None = None
    checks: list[str] | None = None
    schedule: str | None = None
    keywords: list[str] | None = None
    notify: dict[str, Any] | None = None
    enabled: bool | None = None


def _m(m: Monitor) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "display_id": m.display_id,
        "case_id": str(m.case_id),
        "name": m.name,
        "target_value": m.target_value,
        "target_type": m.target_type,
        "checks": m.checks,
        "schedule": m.schedule,
        "enabled": m.enabled,
        "keywords": m.keywords,
        "notify": m.notify,
        "last_run_at": m.last_run_at,
        "next_run_at": m.next_run_at,
        "last_status": m.last_status,
        "last_error": m.last_error,
        "run_count": m.run_count,
        "created_at": m.created_at,
        "has_baseline": bool(m.baseline),
    }


def _a(a: Alert) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "display_id": a.display_id,
        "case_id": str(a.case_id),
        "monitor_id": str(a.monitor_id) if a.monitor_id else None,
        "alert_type": a.alert_type,
        "severity": a.severity,
        "title": a.title,
        "message": a.message,
        "source_label": a.source_label,
        "data": a.data,
        "read": a.read,
        "acknowledged_at": a.acknowledged_at,
        "delivered": a.delivered,
        "detected_at": a.created_at,
    }


@router.get("/monitors")
async def list_monitors(_: CurrentUser, db: DB, case_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    stmt = select(Monitor)
    if case_id:
        stmt = stmt.where(Monitor.case_id == case_id)
    return [_m(m) for m in (await db.execute(stmt.order_by(Monitor.created_at.desc()))).scalars()]


@router.post("/monitors", status_code=status.HTTP_201_CREATED)
async def create_monitor(payload: MonitorCreate, user: Analyst, db: DB) -> dict[str, Any]:
    case = await case_service.get_case(db, payload.case_id)
    value, ttype, tid = payload.target_value, payload.target_type, payload.target_id
    if payload.target_id:
        t = await case_service.get_target(db, payload.target_id)
        if t.case_id != case.id:
            raise NotFoundError("Target not on this case.")
        value, ttype = t.normalized_value, t.type
    if not value:
        from eyohe.core.errors import ValidationError

        raise ValidationError("Provide target_id or target_value.")
    if not ttype:
        from eyohe.enrichment.classify import classify_target

        ttype = str(classify_target(value)[0])
    m = await mon_service.create_monitor(
        db,
        case,
        user,
        name=payload.name,
        target_value=value,
        target_type=ttype,
        checks=payload.checks,
        schedule=payload.schedule,
        keywords=payload.keywords,
        notify=payload.notify,
        target_id=tid,
    )
    await db.commit()
    return _m(m)


@router.get("/monitors/{monitor_id}")
async def get_monitor(monitor_id: str, _: CurrentUser, db: DB) -> dict[str, Any]:
    m = await mon_service.get_monitor(db, monitor_id)
    return {**_m(m), "baseline": m.baseline}


@router.patch("/monitors/{monitor_id}")
async def update_monitor(monitor_id: str, payload: MonitorUpdate, _: Analyst, db: DB) -> dict[str, Any]:
    m = await mon_service.get_monitor(db, monitor_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        if v is None:
            continue
        if k == "schedule":
            m.next_run_at = mon_service.next_run(v)
        setattr(m, k, v)
    await db.commit()
    return _m(m)


@router.delete("/monitors/{monitor_id}")
async def delete_monitor(monitor_id: str, _: Analyst, db: DB) -> dict[str, Any]:
    m = await mon_service.get_monitor(db, monitor_id)
    await db.delete(m)
    await db.commit()
    return {"ok": True}


@router.post("/monitors/{monitor_id}/run")
async def run_monitor_now(monitor_id: str, _: Analyst, db: DB) -> dict[str, Any]:
    m = await mon_service.get_monitor(db, monitor_id)
    from eyohe.orchestrator.jobs import job_manager

    key = await job_manager.enqueue("run_monitor", str(m.id), key=f"monitor:{m.id}")
    return {"queued": True, "job": key}


@router.get("/alerts")
async def list_alerts(
    _: CurrentUser,
    db: DB,
    case_id: uuid.UUID | None = None,
    unread: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
) -> dict[str, Any]:
    stmt = select(Alert)
    if case_id:
        stmt = stmt.where(Alert.case_id == case_id)
    if unread:
        stmt = stmt.where(Alert.read.is_(False))
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await db.execute(stmt.order_by(Alert.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).scalars()
    return {"items": [_a(a) for a in rows], "total": total, "page": page, "page_size": page_size}


@router.post("/alerts/{alert_id}/ack")
async def ack_alert(alert_id: uuid.UUID, user: Analyst, db: DB) -> dict[str, Any]:
    a = await db.get(Alert, alert_id)
    if a is None:
        raise NotFoundError("Alert not found.")
    a.read = True
    a.acknowledged_by = user.id
    a.acknowledged_at = utcnow()
    await db.commit()
    return _a(a)


@router.post("/alerts/read-all")
async def read_all(user: Analyst, db: DB, case_id: uuid.UUID | None = None) -> dict[str, Any]:
    from sqlalchemy import update

    stmt = (
        update(Alert).where(Alert.read.is_(False)).values(read=True, acknowledged_by=user.id, acknowledged_at=utcnow())
    )
    if case_id:
        stmt = stmt.where(Alert.case_id == case_id)
    r = await db.execute(stmt)
    await db.commit()
    return {"updated": int(getattr(r, "rowcount", 0) or 0)}
