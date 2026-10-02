"""Audit logging helper. Every state-changing service call records who did what, to which case."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.db import utcnow
from eyohe.models.auth import AuditLog


async def record_audit(
    session: AsyncSession,
    action: str,
    *,
    actor_id: uuid.UUID | None = None,
    actor_label: str = "system",
    case_id: uuid.UUID | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    detail: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AuditLog:
    ctx = structlog.contextvars.get_contextvars()
    row = AuditLog(
        created_at=utcnow(),
        actor_id=actor_id,
        actor_label=actor_label,
        action=str(action),
        case_id=case_id,
        object_type=object_type,
        object_id=object_id,
        request_id=ctx.get("request_id"),
        ip_address=ip_address,
        detail=detail or {},
    )
    session.add(row)
    return row
