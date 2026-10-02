"""Bounded research agent: PLAN → TOOL → OBSERVE → UPDATE EVIDENCE → DECIDE → VERIFY → COMPLETE.

The model only sees registered tool schemas and tool results. It cannot fetch arbitrary URLs,
cannot assert confidence, and every evidence record it creates is quote-validated. The loop
stops on `finish`, on MAX_AGENT_ITERATIONS, on the runtime bound, or when the analyst pauses/stops."""

from __future__ import annotations

import json
import time
from typing import Any

from sqlalchemy import select

from eyohe.ai.ollama import OllamaClient, OllamaUnavailableError
from eyohe.ai.tools import ToolRuntime, call_tool, tool_specs_for_ollama
from eyohe.core.enums import EventType
from eyohe.core.logging import get_logger, redact_text
from eyohe.models.investigations import Investigation, InvestigationTask
from eyohe.orchestrator.events import emit_event
from eyohe.orchestrator.executors import RunContext

log = get_logger("agent")

SYSTEM = """You are the research component of Eyohe OSINT, a public-source intelligence workstation.
Goal: expand what is publicly known about the investigation target using ONLY the provided tools.

Hard rules:
- Never state facts you did not obtain from a tool result in this run. If something is unknown, say "not found".
- Only fetch URLs that appeared in earlier tool results.
- When you record evidence, the excerpt MUST be copied verbatim from the fetched page text. Do not paraphrase.
- Never invent usernames, dates, account-creation dates, relationships, statistics or sources.
- Community content (Reddit, forums) is a statement by a user, not a fact. Use evidence_type PUBLIC_STATEMENT or ALLEGATION.
- Identity conclusions ("X is the same person as Y") are proposals for the analyst, never certainties.
- Public sources only: never attempt to bypass logins, paywalls, CAPTCHAs or rate limits.
- Prefer breadth of independent sources over depth on one page. Stop (call finish) when results repeat or budgets are near.
Work in short steps: decide the single most useful next tool call, observe, then decide again."""


class ResearchAgent:
    def __init__(self, ctx: RunContext, task: InvestigationTask) -> None:
        self.ctx = ctx
        self.task = task
        self.client = OllamaClient()
        self.rt = ToolRuntime(ctx=ctx, task=task)
        self.max_iters = int(ctx.bounds.get("max_agent_iterations", 50))
        self.deadline = time.monotonic() + min(int(ctx.bounds.get("max_runtime_seconds", 1800)) // 2, 900)

    async def _seed_allowed_urls(self) -> None:
        from eyohe.models.sources import Source

        rows = await self.ctx.session.execute(select(Source.url).where(Source.case_id == self.ctx.case.id))
        self.rt.allow([u for (u,) in rows.all()])

    async def _known_context(self) -> str:
        from eyohe.ai.retrieval import case_context

        c = await case_context(self.ctx.session, self.ctx.case.id)
        from eyohe.models.entities import Entity

        ents = list(
            (
                await self.ctx.session.execute(
                    select(Entity)
                    .where(Entity.case_id == self.ctx.case.id)
                    .order_by(Entity.source_count.desc())
                    .limit(40)
                )
            ).scalars()
        )
        return json.dumps(
            {
                **c,
                "known_entities": [f"{e.type}:{e.value}" for e in ents],
                "discovered_targets": self.ctx.investigation.stats.get("discovered_targets", [])[:20],
            },
            default=str,
        )

    async def run(self) -> dict[str, Any]:
        inv: Investigation = self.ctx.investigation
        if not await self.client.available():
            raise OllamaUnavailableError(
                "Ollama is not reachable; the AI research loop cannot run (collectors still ran)."
            )
        await self._seed_allowed_urls()
        depth = int(self.ctx.bounds.get("max_research_depth", 2))
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": f"Objective: {inv.objective}\nTarget: {self.ctx.target.type} {self.ctx.target.normalized_value}\nResearch depth allowed: {depth} (0 = target only, 1 = also entities directly linked to it, 2 = one more hop).\nIteration budget: {self.max_iters}.\nCurrent case knowledge (do not restate as new findings): {await self._known_context()}",
            },
        ]
        tools = tool_specs_for_ollama()
        iterations = 0
        tool_calls = 0
        errors = 0
        summary = ""
        last_results: list[str] = []
        while iterations < self.max_iters and time.monotonic() < self.deadline:
            iterations += 1
            flag = (
                await self.ctx.session.execute(select(Investigation.control_flag).where(Investigation.id == inv.id))
            ).scalar_one()
            if flag in ("pause", "stop"):
                summary = f"stopped by analyst ({flag})"
                break
            try:
                resp = await self.client.chat(
                    messages, tools=tools, purpose="research_agent", temperature=0.2, max_tokens=1200
                )
            except OllamaUnavailableError as exc:
                await emit_event(
                    self.ctx.session,
                    inv,
                    EventType.WARNING,
                    "AI",
                    f"AI research loop interrupted: {exc.message}",
                    level="warning",
                    task_id=self.task.id,
                )
                summary = f"interrupted: {exc.message}"
                break
            msg = resp.get("message", {})
            calls = msg.get("tool_calls") or []
            content = (msg.get("content") or "").strip()
            messages.append({"role": "assistant", "content": content, **({"tool_calls": calls} if calls else {})})
            if content and not calls:
                # A bare message without tools: treat as the agent's narration/summary.
                await emit_event(
                    self.ctx.session, inv, EventType.AI_MESSAGE, "AI", redact_text(content)[:400], task_id=self.task.id
                )
                if any(k in content.lower() for k in ("diminishing", "complete", "finished", "no further")):
                    summary = content[:1200]
                    break
                messages.append(
                    {"role": "user", "content": "Continue with a tool call, or call finish with a summary."}
                )
                continue
            if not calls:
                messages.append({"role": "user", "content": "Use a tool or call finish."})
                continue
            finished = False
            for call in calls[:3]:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                tool_calls += 1
                await emit_event(
                    self.ctx.session,
                    inv,
                    EventType.AI_TOOL_CALL,
                    "AI",
                    f"tool {name}({redact_text(json.dumps(args))[:160]})",
                    task_id=self.task.id,
                    data={"tool": name, "args": args},
                )
                result = await call_tool(self.rt, name, args)
                if "error" in result:
                    errors += 1
                    await emit_event(
                        self.ctx.session,
                        inv,
                        EventType.WARNING,
                        "AI",
                        f"{name}: {result['error']}"[:300],
                        level="warning",
                        task_id=self.task.id,
                    )
                payload = json.dumps(result, default=str)
                if len(payload) > 6000:
                    payload = payload[:6000] + "...(truncated)"
                last_results.append(payload[:200])
                messages.append({"role": "tool", "content": payload, "tool_name": name})
                if name == "finish" and result.get("done"):
                    summary = str(result.get("summary", ""))[:1500]
                    finished = True
                    break
            if finished:
                break
            if errors >= 8:
                summary = "stopped: too many tool errors"
                break
            # Keep the context bounded: drop the oldest tool exchanges beyond ~24 messages.
            if len(messages) > 26:
                messages = messages[:2] + messages[-22:]
        else:
            summary = summary or (
                "iteration budget reached" if iterations >= self.max_iters else "runtime bound reached"
            )
        await emit_event(
            self.ctx.session,
            inv,
            EventType.AI_MESSAGE,
            "AI",
            f"Research loop finished after {iterations} iteration(s), {tool_calls} tool call(s): {summary[:200]}",
            task_id=self.task.id,
            data={"iterations": iterations, "tool_calls": tool_calls, "errors": errors},
        )
        return {
            "iterations": iterations,
            "tool_calls": tool_calls,
            "errors": errors,
            "evidence": len(self.rt.created_evidence),
            "findings": len(self.rt.created_findings),
            "summary": summary[:1500],
            "tool_usage": dict(self.rt.calls),
        }
