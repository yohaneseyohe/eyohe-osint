from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from eyohe.api.deps import DB
from eyohe.services.health import check_database, full_health

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(db: DB) -> dict[str, Any]:
    return await full_health(db)


@router.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(db: DB) -> dict[str, Any]:
    h = await check_database(db)
    return {"status": "ok" if h.status == "ONLINE" else "not_ready", "database": h.status}


@router.get("/metrics", include_in_schema=False)
async def metrics() -> PlainTextResponse:
    return PlainTextResponse(generate_latest().decode(), media_type=CONTENT_TYPE_LATEST)
