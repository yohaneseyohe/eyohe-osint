"""arq worker entrypoint and the job function table shared with the embedded runner."""

from __future__ import annotations

from typing import Any

from eyohe.core.config import get_settings
from eyohe.core.logging import configure_logging


async def run_investigation_job(ctx: Any, investigation_id: str) -> None:
    from eyohe.orchestrator.runner import run_investigation

    await run_investigation(investigation_id)


async def plan_investigation_job(ctx: Any, investigation_id: str, use_ai: bool = True) -> None:
    from eyohe.services.investigations import plan_investigation_background

    await plan_investigation_background(investigation_id, use_ai=use_ai)


async def run_monitor_job(ctx: Any, monitor_id: str) -> None:
    from eyohe.scheduler.monitors import run_monitor

    await run_monitor(monitor_id)


async def generate_report_job(ctx: Any, report_id: str) -> None:
    from eyohe.reporting.service import generate_report

    await generate_report(report_id)


JOB_FUNCTIONS = {
    "run_investigation": run_investigation_job,
    "plan_investigation": plan_investigation_job,
    "run_monitor": run_monitor_job,
    "generate_report": generate_report_job,
}


async def _startup(ctx: Any) -> None:
    configure_logging()


def _redis_settings() -> Any:
    from arq.connections import RedisSettings

    return RedisSettings.from_dsn(get_settings().redis_url)


class WorkerSettings:
    functions = list(JOB_FUNCTIONS.values())
    on_startup = _startup
    max_jobs = 2  # resource-constrained workstation
    job_timeout = 3600
    redis_settings = _redis_settings()
