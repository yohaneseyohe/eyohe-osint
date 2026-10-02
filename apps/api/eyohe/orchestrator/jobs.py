"""Job manager: runs investigation/monitor jobs either in-process (embedded) or via arq.

Both paths call the same coroutines so behaviour is identical; only scheduling differs.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from eyohe.core.config import get_settings
from eyohe.core.logging import get_logger

log = get_logger("jobs")

JobFn = Callable[..., Awaitable[Any]]


class JobManager:
    def __init__(self) -> None:
        self._tasks: dict[str, asyncio.Task[Any]] = {}
        self._redis_pool: Any = None
        self._started = False
        self._scheduler_task: asyncio.Task[Any] | None = None

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        settings = get_settings()
        if settings.job_backend == "arq":
            try:
                from arq import create_pool
                from arq.connections import RedisSettings

                self._redis_pool = await create_pool(RedisSettings.from_dsn(settings.redis_url))
            except Exception as exc:
                log.error("arq_pool_failed", error=str(exc))
                self._redis_pool = None
        if settings.job_backend == "embedded" and settings.eyohe_env != "test":
            from eyohe.scheduler.runner import scheduler_loop

            self._scheduler_task = asyncio.create_task(scheduler_loop(), name="eyohe-scheduler")

    async def stop(self) -> None:
        for t in list(self._tasks.values()):
            t.cancel()
        if self._scheduler_task:
            self._scheduler_task.cancel()
        if self._redis_pool is not None:
            await self._redis_pool.aclose()
        self._started = False

    async def enqueue(self, job_name: str, *args: Any, key: str | None = None) -> str:
        """Schedule a job. Returns a job id. In embedded mode the coroutine runs in the API process."""
        settings = get_settings()
        key = key or f"{job_name}:{args[0] if args else uuid.uuid4().hex}"
        if settings.job_backend == "arq" and self._redis_pool is not None:
            job = await self._redis_pool.enqueue_job(job_name, *args, _job_id=key)
            return job.job_id if job else key
        from eyohe.worker import JOB_FUNCTIONS

        fn = JOB_FUNCTIONS[job_name]
        existing = self._tasks.get(key)
        if existing and not existing.done():
            return key

        async def _run() -> None:
            try:
                await fn(None, *args)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("embedded_job_failed", job=job_name, error=str(exc))
            finally:
                self._tasks.pop(key, None)

        self._tasks[key] = asyncio.create_task(_run(), name=key)
        return key

    def is_running(self, key: str) -> bool:
        t = self._tasks.get(key)
        return bool(t and not t.done())

    def cancel(self, key: str) -> bool:
        t = self._tasks.get(key)
        if t and not t.done():
            t.cancel()
            return True
        return False


job_manager = JobManager()
