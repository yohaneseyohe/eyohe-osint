"""Executor for the 'correlate' task: cross-collector entity resolution."""

from __future__ import annotations

from typing import Any

from eyohe.enrichment.resolve import correlate_case
from eyohe.models.investigations import InvestigationTask
from eyohe.orchestrator.executors import RunContext, register_executor


@register_executor("correlate")
async def correlate_executor(ctx: RunContext, task: InvestigationTask) -> dict[str, Any]:
    out = await correlate_case(ctx.session, ctx.case.id)
    if out["relationships"]:
        await ctx.collect_context(task).log(
            "GRAPH",
            f"{out['relationships']} relationship proposal(s) from entity correlation "
            "(analyst review required for identity links)",
            proposals=out["proposals"][:10],
        )
    out["note"] = "no new correlations" if not out["relationships"] else ""
    return out
