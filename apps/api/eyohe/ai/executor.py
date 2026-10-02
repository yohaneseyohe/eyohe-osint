"""Executors for AI-driven tasks: research_agent and summarize."""

from __future__ import annotations

from typing import Any

from eyohe.ai.agent import ResearchAgent
from eyohe.ai.summarizer import draft_findings
from eyohe.core.enums import EventType
from eyohe.models.investigations import InvestigationTask
from eyohe.orchestrator.events import emit_event
from eyohe.orchestrator.executors import RunContext, register_executor


@register_executor("research_agent")
async def research_agent_executor(ctx: RunContext, task: InvestigationTask) -> dict[str, Any]:
    return await ResearchAgent(ctx, task).run()


@register_executor("summarize")
async def summarize_executor(ctx: RunContext, task: InvestigationTask) -> dict[str, Any]:
    out = await draft_findings(ctx.session, ctx.case.id, investigation_id=ctx.investigation.id)
    if out.get("created"):
        await emit_event(
            ctx.session,
            ctx.investigation,
            EventType.FINDING_CREATED,
            "AI",
            f"{out['created']} AI-drafted finding(s) created from evidence (confidence computed by the engine)",
            task_id=task.id,
            data=out,
            commit=False,
        )
    if out.get("skipped"):
        from eyohe.core.errors import ConfigurationError

        raise ConfigurationError(out["note"])
    out["findings"] = out.get("created", 0)
    return out
