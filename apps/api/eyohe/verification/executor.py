"""Executor for the 'verify' task: recompute evidence-based confidence and detect contradictions."""

from __future__ import annotations

from typing import Any

from eyohe.models.investigations import InvestigationTask
from eyohe.orchestrator.executors import RunContext, register_executor
from eyohe.verification.service import verify_case


@register_executor("verify")
async def verify_executor(ctx: RunContext, task: InvestigationTask) -> dict[str, Any]:
    out = await verify_case(ctx.session, ctx.case.id, ctx.investigation)
    out["note"] = "confidence recomputed from evidence"
    return out
