"""Embedded scheduler loop: polls due monitors (Phase 9 implements run_monitor)."""

from __future__ import annotations

import asyncio

from eyohe.core.logging import get_logger

log = get_logger("scheduler")


async def scheduler_loop(interval_seconds: int = 60) -> None:
    from eyohe.scheduler.monitors import run_due_monitors

    while True:
        try:
            await run_due_monitors()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("scheduler_tick_failed", error=str(exc))
        await asyncio.sleep(interval_seconds)
