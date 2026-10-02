"""Audit log, settings (non-secret), dashboard statistics, collectors."""

from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from eyohe.api.deps import DB, Admin, CurrentUser
from eyohe.collectors.registry import collector_registry
from eyohe.core.config import get_settings
from eyohe.core.db import utcnow
from eyohe.core.enums import AuditAction
from eyohe.models.auth import AuditLog, SystemSetting
from eyohe.models.cases import Case
from eyohe.models.entities import Entity, Relationship
from eyohe.models.evidence import Evidence
from eyohe.models.findings import Finding
from eyohe.models.investigations import Investigation, InvestigationEvent
from eyohe.models.monitoring import Alert
from eyohe.models.sources import Source
from eyohe.services.audit import record_audit

router = APIRouter(tags=["system"])

EDITABLE_SETTINGS = {
    "ollama_model": str,
    "search_providers": str,
    "max_agent_iterations": int,
    "max_research_depth": int,
    "max_queries": int,
    "max_pages": int,
    "max_runtime_seconds": int,
    "max_results_per_source": int,
    "report_classification": str,
    "evidence_retention_days": int,
    "graph_backend": str,
}


@router.get("/audit")
async def audit(
    _: CurrentUser,
    db: DB,
    case_id: uuid.UUID | None = None,
    action: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    stmt = select(AuditLog)
    if case_id:
        stmt = stmt.where(AuditLog.case_id == case_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    total = int((await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one())
    rows = (
        await db.execute(stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).scalars()
    return {
        "items": [
            {
                "id": str(r.id),
                "created_at": r.created_at,
                "actor": r.actor_label,
                "action": r.action,
                "case_id": str(r.case_id) if r.case_id else None,
                "object_type": r.object_type,
                "object_id": r.object_id,
                "request_id": r.request_id,
                "detail": r.detail,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/settings")
async def get_settings_view(_: CurrentUser, db: DB) -> dict[str, Any]:
    s = get_settings()
    overrides = {row.key: row.value.get("value") for row in (await db.execute(select(SystemSetting))).scalars()}
    return {
        "env": s.public_view(),
        "overrides": overrides,
        "editable": sorted(EDITABLE_SETTINGS),
        "note": "Secrets are configured in .env only and are never returned by the API.",
    }


@router.patch("/settings")
async def update_settings(payload: dict[str, Any], admin: Admin, db: DB) -> dict[str, Any]:
    from eyohe.core.errors import ValidationError

    applied = {}
    for k, v in payload.items():
        if k not in EDITABLE_SETTINGS:
            raise ValidationError(f"Setting '{k}' is not editable at runtime (set it in .env).")
        caster = EDITABLE_SETTINGS[k]
        try:
            val = caster(v)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Invalid value for {k}") from exc
        row = await db.get(SystemSetting, k)
        if row is None:
            row = SystemSetting(key=k, value={"value": val}, updated_at=utcnow(), updated_by=admin.username)
            db.add(row)
        else:
            row.value = {"value": val}
            row.updated_at = utcnow()
            row.updated_by = admin.username
        setattr(get_settings(), k, val)  # live override for this process
        applied[k] = val
    await record_audit(
        db, AuditAction.CONFIG_CHANGED, actor_id=admin.id, actor_label=admin.username, detail={"changes": applied}
    )
    await db.commit()
    return {"applied": applied}


@router.get("/collectors")
async def collectors(_: CurrentUser) -> list[dict[str, Any]]:
    health = await collector_registry.health_all()
    return [
        {
            "name": c.name,
            "description": c.description,
            "tier": c.source_tier,
            "targets": sorted(c.supported_targets),
            "stage": c.stage,
            "requires_internet": c.requires_internet,
            "health": asdict(health[c.name]) if c.name in health else None,
        }
        for c in collector_registry.all()
    ]


@router.get("/dashboard")
async def dashboard(_: CurrentUser, db: DB) -> dict[str, Any]:
    async def count(model: Any, *where: Any) -> int:
        return int((await db.execute(select(func.count()).select_from(model).where(*where))).scalar_one())

    status_rows = (await db.execute(select(Case.status, func.count()).group_by(Case.status))).all()
    inv_rows = (await db.execute(select(Investigation.status, func.count()).group_by(Investigation.status))).all()
    src_rows = (await db.execute(select(Source.source_type, func.count()).group_by(Source.source_type))).all()
    tier_rows = (await db.execute(select(Source.tier, func.count()).group_by(Source.tier))).all()
    conf_rows = (await db.execute(select(Finding.confidence, func.count()).group_by(Finding.confidence))).all()
    ent_rows = (await db.execute(select(Entity.type, func.count()).group_by(Entity.type))).all()
    recent_findings = (await db.execute(select(Finding).order_by(Finding.created_at.desc()).limit(8))).scalars()
    recent_events = (
        await db.execute(select(InvestigationEvent).order_by(InvestigationEvent.created_at.desc()).limit(30))
    ).scalars()
    active = (
        await db.execute(
            select(Investigation)
            .where(Investigation.status.in_(["RUNNING", "VERIFYING", "PAUSED", "AWAITING_APPROVAL", "PLANNING"]))
            .order_by(Investigation.updated_at.desc())
            .limit(10)
        )
    ).scalars()
    unread_alerts = await count(Alert, Alert.read.is_(False))
    return {
        "cases": {"total": await count(Case), "by_status": dict(status_rows)},
        "investigations": {"total": await count(Investigation), "by_status": dict(inv_rows)},
        "evidence": await count(Evidence),
        "sources": await count(Source),
        "entities": await count(Entity),
        "relationships": await count(Relationship),
        "findings": await count(Finding),
        "unread_alerts": unread_alerts,
        "source_distribution": dict(src_rows),
        "source_tiers": {str(k): v for k, v in tier_rows},
        "finding_confidence": dict(conf_rows),
        "entity_types": dict(ent_rows),
        "recent_findings": [
            {
                "id": str(f.id),
                "display_id": f.display_id,
                "case_id": str(f.case_id),
                "title": f.title,
                "confidence": f.confidence,
                "created_at": f.created_at,
            }
            for f in recent_findings
        ],
        "recent_events": [
            {
                "id": str(e.id),
                "investigation_id": str(e.investigation_id),
                "case_id": str(e.case_id),
                "created_at": e.created_at,
                "event_type": e.event_type,
                "stage": e.stage,
                "message": e.message,
                "level": e.level,
            }
            for e in recent_events
        ],
        "active_investigations": [
            {
                "id": str(i.id),
                "display_id": i.display_id,
                "case_id": str(i.case_id),
                "name": i.name,
                "status": i.status,
                "updated_at": i.updated_at,
            }
            for i in active
        ],
    }
