"""Task executors: map a planned task type to the code that performs it.

Collector-backed tasks share one generic executor; composite tasks (search, correlation,
verification, AI research, summarisation) have dedicated executors registered by later phases.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.collectors.base import CollectContext
from eyohe.collectors.registry import collector_registry
from eyohe.core.enums import EventType, TargetType
from eyohe.core.errors import ConfigurationError
from eyohe.models.cases import Case, Target
from eyohe.models.investigations import Investigation, InvestigationTask
from eyohe.orchestrator.events import emit_event
from eyohe.orchestrator.persist import persist_result


@dataclass
class RunContext:
    session: AsyncSession
    investigation: Investigation
    case: Case
    target: Target
    bounds: dict[str, Any] = field(default_factory=dict)

    def collect_context(self, task: InvestigationTask) -> CollectContext:
        inv = self.investigation

        async def _emit(stage: str, message: str, data: dict[str, Any]) -> None:
            await emit_event(
                self.session, inv, EventType.INFO, stage, message, task_id=task.id, data=data, commit=False
            )

        return CollectContext(
            case_id=str(self.case.id),
            investigation_id=str(inv.id),
            task_id=str(task.id),
            params=dict(task.params),
            max_results=int(self.bounds.get("max_results_per_source", 20)),
            emit=_emit,
        )

    def task_target(self, task: InvestigationTask) -> tuple[TargetType, str]:
        """Tasks may override the value (e.g. DNS of an email's domain)."""
        ttype = TargetType(self.target.type)
        value = self.target.normalized_value
        if task.params.get("value"):
            return TargetType.DOMAIN if ttype == TargetType.EMAIL else ttype, str(task.params["value"])
        if task.params.get("handle"):
            return TargetType.USERNAME, str(task.params["handle"])
        if task.params.get("from_url") and ttype == TargetType.URL:
            from eyohe.core.urlnorm import host_of

            return TargetType.DOMAIN, host_of(value)
        return ttype, value


Executor = Callable[[RunContext, InvestigationTask], Awaitable[dict[str, Any]]]
_EXECUTORS: dict[str, Executor] = {}


def register_executor(task_type: str) -> Callable[[Executor], Executor]:
    def deco(fn: Executor) -> Executor:
        _EXECUTORS[task_type] = fn
        return fn

    return deco


async def collector_executor(ctx: RunContext, task: InvestigationTask) -> dict[str, Any]:
    collector = collector_registry.get(task.task_type)
    if collector is None:
        raise ConfigurationError(f"Collector '{task.task_type}' is not available in this build.")
    ttype, value = ctx.task_target(task)
    if not collector.supports(ttype):
        return {"note": f"collector {collector.name} does not apply to {ttype} targets", "skipped": True}
    result = await collector.collect(ctx.collect_context(task), ttype, value)
    stats = await persist_result(ctx.session, ctx.investigation, task, result)
    out = {**stats.to_dict(), **result.summary}
    if result.warnings:
        out["warnings"] = result.warnings[:20]
        for w in result.warnings[:5]:
            await emit_event(
                ctx.session,
                ctx.investigation,
                EventType.WARNING,
                collector.stage,
                w[:300],
                level="warning",
                task_id=task.id,
                commit=False,
            )
    return out


def get_executor(task_type: str) -> Executor | None:
    _load_builtin()
    if task_type in _EXECUTORS:
        return _EXECUTORS[task_type]
    if collector_registry.get(task_type) is not None:
        return collector_executor
    return None


_loaded = False


def _load_builtin() -> None:
    global _loaded
    if _loaded:
        return
    _loaded = True
    # Side-effect imports register executors for composite tasks.
    import contextlib

    for mod in (
        "eyohe.search.executor",
        "eyohe.enrichment.executor",
        "eyohe.verification.executor",
        "eyohe.ai.executor",
    ):
        with contextlib.suppress(ImportError):
            __import__(mod)


def target_uuid(ctx: RunContext) -> uuid.UUID:
    return ctx.target.id
