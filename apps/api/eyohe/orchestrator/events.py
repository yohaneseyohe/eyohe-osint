"""Investigation event emission and live fan-out.

Events are persisted first (append-only with a per-investigation sequence), then broadcast to
in-process subscribers and, when Redis is reachable, published on a channel so an API process can
relay events produced by a separate worker. SSE clients replay from the DB using ``last_seq`` and
then follow the live stream, so nothing is lost or invented.
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

import orjson
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.config import get_settings
from eyohe.core.db import get_session_factory, utcnow
from eyohe.core.logging import get_logger, redact_text
from eyohe.models.investigations import Investigation, InvestigationEvent

log = get_logger("events")


def event_to_dict(e: InvestigationEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "investigation_id": str(e.investigation_id),
        "case_id": str(e.case_id),
        "seq": e.seq,
        "created_at": e.created_at.isoformat(),
        "event_type": e.event_type,
        "stage": e.stage,
        "message": e.message,
        "level": e.level,
        "task_id": str(e.task_id) if e.task_id else None,
        "data": e.data,
    }


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._redis: Any = None
        self._redis_checked = False

    async def _get_redis(self) -> Any:
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        if get_settings().eyohe_env == "test":
            return None
        try:
            import redis.asyncio as aioredis

            r = aioredis.from_url(  # type: ignore[no-untyped-call]
                get_settings().redis_url, socket_connect_timeout=1, socket_timeout=1
            )
            await r.ping()
            self._redis = r
        except Exception:
            self._redis = None
        return self._redis

    async def publish(self, payload: dict[str, Any]) -> None:
        inv = payload["investigation_id"]
        for q in list(self._subs.get(inv, ())):
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(payload)
        for q in list(self._subs.get("*", ())):
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(payload)
        r = await self._get_redis()
        if r is not None:
            with contextlib.suppress(Exception):
                await r.publish("eyohe:events", orjson.dumps(payload))

    @contextlib.asynccontextmanager
    async def subscription(self, investigation_id: str) -> AsyncIterator[asyncio.Queue[dict[str, Any]]]:
        """Queue-based subscription. Consumers use ``asyncio.wait_for(queue.get(), timeout)`` for
        heartbeats; cancelling a pending ``get`` is safe, unlike cancelling an async generator."""
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        self._subs[investigation_id].add(q)
        relay: asyncio.Task[None] | None = None
        r = await self._get_redis()
        if r is not None and get_settings().job_backend == "arq":
            relay = asyncio.create_task(self._relay_redis(investigation_id, q))
        try:
            yield q
        finally:
            self._subs[investigation_id].discard(q)
            if relay:
                relay.cancel()

    async def subscribe(self, investigation_id: str) -> AsyncIterator[dict[str, Any]]:
        async with self.subscription(investigation_id) as q:
            while True:
                yield await q.get()

    async def _relay_redis(self, investigation_id: str, q: asyncio.Queue[dict[str, Any]]) -> None:
        r = await self._get_redis()
        if r is None:
            return
        pubsub = r.pubsub()
        await pubsub.subscribe("eyohe:events")
        try:
            async for msg in pubsub.listen():
                if msg.get("type") != "message":
                    continue
                payload = orjson.loads(msg["data"])
                if investigation_id in ("*", payload.get("investigation_id")):
                    with contextlib.suppress(asyncio.QueueFull):
                        q.put_nowait(payload)
        finally:
            with contextlib.suppress(Exception):
                await pubsub.unsubscribe("eyohe:events")
                await pubsub.aclose()


event_bus = EventBus()


async def emit_event(
    session: AsyncSession,
    investigation: Investigation,
    event_type: str,
    stage: str,
    message: str,
    *,
    level: str = "info",
    task_id: uuid.UUID | None = None,
    data: dict[str, Any] | None = None,
    commit: bool = True,
) -> InvestigationEvent:
    """Persist an event with the next sequence number and broadcast it."""
    # Atomic increment of the per-investigation counter.
    result = await session.execute(
        update(Investigation)
        .where(Investigation.id == investigation.id)
        .values(event_seq=Investigation.event_seq + 1)
        .returning(Investigation.event_seq)
    )
    seq = int(result.scalar_one())
    ev = InvestigationEvent(
        investigation_id=investigation.id,
        case_id=investigation.case_id,
        seq=seq,
        created_at=utcnow(),
        event_type=str(event_type),
        stage=stage,
        message=redact_text(message)[:4000],
        level=level,
        task_id=task_id,
        data=_safe_json(data or {}),
    )
    session.add(ev)
    if commit:
        await session.commit()
    else:
        await session.flush()
    await event_bus.publish(event_to_dict(ev))
    return ev


def _safe_json(data: dict[str, Any]) -> dict[str, Any]:
    try:
        out: dict[str, Any] = orjson.loads(orjson.dumps(data, default=str))
        return out
    except Exception:
        return {"repr": repr(data)[:2000]}


async def replay_events(investigation_id: uuid.UUID, after_seq: int = 0, limit: int = 500) -> list[dict[str, Any]]:
    async with get_session_factory()() as s:
        rows = (
            await s.execute(
                select(InvestigationEvent)
                .where(InvestigationEvent.investigation_id == investigation_id, InvestigationEvent.seq > after_seq)
                .order_by(InvestigationEvent.seq)
                .limit(limit)
            )
        ).scalars()
        return [event_to_dict(e) for e in rows]
