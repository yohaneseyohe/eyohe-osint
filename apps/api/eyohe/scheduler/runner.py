"""Embedded scheduler loop: polls due monitors (Phase 9 implements run_monitor)."""

from __future__ import annotations

import asyncio

from eyohe.core.logging import get_logger

log = get_logger("scheduler")


async def scheduler_loop(interval_seconds: int = 60) -> None:
    from eyohe.scheduler.monitors import run_due_monitors

    ticks = 0
    while True:
        try:
            await run_due_monitors()
            ticks += 1
            if ticks % 60 == 1:  # roughly hourly
                await apply_retention()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("scheduler_tick_failed", error=str(exc))
        await asyncio.sleep(interval_seconds)


async def apply_retention() -> int:
    """Purge vault artifacts older than EVIDENCE_RETENTION_DAYS (0 = keep forever)."""
    from datetime import UTC, datetime, timedelta

    from eyohe.core.config import get_settings
    from eyohe.services.vault import get_vault

    days = get_settings().evidence_retention_days
    if days <= 0:
        return 0
    n = get_vault().purge_older_than(datetime.now(UTC) - timedelta(days=days))
    if n:
        log.info("retention_purge", files=n, days=days)
    return n
