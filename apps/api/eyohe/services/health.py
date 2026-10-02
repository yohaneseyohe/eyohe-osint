"""System health: API, database, Redis, Ollama, search, collectors, graph, storage, internet."""

from __future__ import annotations

import asyncio
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe import __version__
from eyohe.core.config import get_settings


@dataclass
class ComponentHealth:
    name: str
    status: str  # ONLINE | OFFLINE | DEGRADED | OPTIONAL | NOT_CONFIGURED
    message: str = ""
    latency_ms: int | None = None
    detail: dict[str, Any] = field(default_factory=dict)
    optional: bool = False


async def check_database(session: AsyncSession) -> ComponentHealth:
    s = get_settings()
    t = time.perf_counter()
    try:
        await session.execute(text("SELECT 1"))
        return ComponentHealth(
            "database",
            "ONLINE",
            "SQLite (development)" if s.is_sqlite else "PostgreSQL",
            int((time.perf_counter() - t) * 1000),
        )
    except Exception as exc:
        return ComponentHealth("database", "OFFLINE", f"{type(exc).__name__}: {exc}"[:300])


async def check_redis() -> ComponentHealth:
    s = get_settings()
    t = time.perf_counter()
    try:
        import redis.asyncio as aioredis

        r = aioredis.from_url(s.redis_url, socket_connect_timeout=1.5, socket_timeout=1.5)  # type: ignore[no-untyped-call]
        try:
            await r.ping()
        finally:
            await r.aclose()
        return ComponentHealth("redis", "ONLINE", "", int((time.perf_counter() - t) * 1000), optional=True)
    except Exception as exc:
        msg = "Redis unreachable; caching and the arq worker are unavailable (embedded jobs still work)."
        return ComponentHealth("redis", "OFFLINE", msg, detail={"error": str(exc)[:200]}, optional=True)


async def check_ollama() -> ComponentHealth:
    s = get_settings()
    t = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{s.ollama_url.rstrip('/')}/api/tags")
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
        have = any(m == s.ollama_model or m.split(":")[0] == s.ollama_model.split(":")[0] for m in models)
        status = "ONLINE" if have else "DEGRADED"
        msg = (
            f"model {s.ollama_model} ready"
            if have
            else f"model {s.ollama_model} not pulled (ollama pull {s.ollama_model})"
        )
        return ComponentHealth(
            "ollama",
            status,
            msg,
            int((time.perf_counter() - t) * 1000),
            {"models": models, "configured_model": s.ollama_model},
            optional=True,
        )
    except Exception as exc:
        return ComponentHealth(
            "ollama",
            "OFFLINE",
            "Ollama not reachable; AI planning/analysis unavailable, collectors still work.",
            detail={"error": str(exc)[:200], "url": s.ollama_url},
            optional=True,
        )


async def check_search() -> ComponentHealth:
    from eyohe.search.providers import provider_health

    return await provider_health()


async def check_collectors() -> ComponentHealth:
    from eyohe.collectors.registry import collector_registry

    results = await collector_registry.health_all()
    online = sum(1 for r in results.values() if r.status == "ONLINE")
    total = len(results)
    status = "ONLINE" if online == total else ("DEGRADED" if online else "OFFLINE")
    return ComponentHealth(
        "collectors",
        status,
        f"{online}/{total} collectors ready",
        detail={k: asdict(v) for k, v in results.items()},
    )


async def check_graph() -> ComponentHealth:
    s = get_settings()
    if s.graph_backend == "postgresql":
        return ComponentHealth("graph", "ONLINE", "PostgreSQL graph backend (relational)", optional=True)
    try:
        from eyohe.graph.neo4j_backend import Neo4jGraphBackend

        ok = await Neo4jGraphBackend().ping()
        return ComponentHealth("graph", "ONLINE" if ok else "OFFLINE", "Neo4j", optional=True)
    except Exception as exc:
        return ComponentHealth("graph", "OFFLINE", f"Neo4j: {exc}"[:200], optional=True)


def check_storage() -> ComponentHealth:
    s = get_settings()
    try:
        s.data_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("evidence", "reports", "screenshots", "exports", "cache"):
            (s.data_dir / sub).mkdir(exist_ok=True)
        usage = shutil.disk_usage(s.data_dir)
        free_gb = usage.free / 1e9
        writable = os.access(s.data_dir, os.W_OK)
        status = "ONLINE" if writable and free_gb > 1 else "DEGRADED"
        return ComponentHealth(
            "storage",
            status,
            f"{free_gb:.1f} GB free at {s.data_dir}",
            detail={"path": str(s.data_dir), "free_gb": round(free_gb, 1), "writable": writable},
        )
    except Exception as exc:
        return ComponentHealth("storage", "OFFLINE", str(exc)[:200])


async def check_internet() -> ComponentHealth:
    t = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            r = await client.head("https://www.example.com/")
            ok = r.status_code < 500
        return ComponentHealth("internet", "ONLINE" if ok else "DEGRADED", "", int((time.perf_counter() - t) * 1000))
    except Exception:
        return ComponentHealth("internet", "OFFLINE", "No Internet connectivity; online collectors are OFFLINE.")


async def full_health(session: AsyncSession) -> dict[str, Any]:
    s = get_settings()
    db, redis_h, ollama, search, collectors, graph, internet = await asyncio.gather(
        check_database(session),
        check_redis(),
        check_ollama(),
        check_search(),
        check_collectors(),
        check_graph(),
        check_internet(),
    )
    components = [
        ComponentHealth("api", "ONLINE", f"v{__version__}"),
        db,
        redis_h,
        ollama,
        search,
        collectors,
        graph,
        check_storage(),
        internet,
    ]
    required_ok = all(c.status == "ONLINE" for c in components if not c.optional and c.name != "internet")
    overall = "ONLINE" if required_ok else "DEGRADED"
    if db.status != "ONLINE":
        overall = "OFFLINE"
    return {
        "status": overall,
        "version": __version__,
        "environment": s.eyohe_env,
        "job_backend": s.job_backend,
        "graph_backend": s.graph_backend,
        "components": [asdict(c) for c in components],
    }
