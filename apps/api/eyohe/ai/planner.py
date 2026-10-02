"""LLM plan adaptation. The model may only reorder/disable catalogue tasks, add search branches and
write rationale. It cannot invent task types, and the template remains the fallback."""

from __future__ import annotations

from typing import Any

from eyohe.ai.ollama import OllamaClient
from eyohe.orchestrator.planner import Plan, PlannedTask

_SCHEMA = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string"},
        "disable_task_types": {"type": "array", "items": {"type": "string"}},
        "additional_search_branches": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["rationale", "additional_search_branches"],
}

SYSTEM = (
    "You tune an OSINT investigation plan. Reply with compact JSON only. "
    "rationale: 1-2 sentences tying the plan to the objective. "
    "disable_task_types: task types from the list that are irrelevant to the objective (never dns/rdap/ct_logs for domains, never verify/correlate). "
    "additional_search_branches: at most 4 focused public-web search queries (operators like site:, filetype:, quotes allowed). "
    "Never invent facts about the target. Public sources only."
)


async def adapt_plan_with_ai(plan: Plan, objective: str) -> tuple[Plan, str]:
    client = OllamaClient()
    if not await client.available():
        return plan, ""
    import json

    user = {
        "objective": objective,
        "target_type": plan.target_type,
        "target_value": plan.target_value,
        "task_types": [t.task_type for t in plan.tasks],
        "existing_search_branches": plan.branches[:8],
    }
    out: dict[str, Any] = await client.chat_json(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(user)}],
        schema=_SCHEMA,
        purpose="plan",
        max_tokens=320,
        num_ctx=2048,
    )
    protected = {"verify", "correlate"}
    if plan.target_type == "DOMAIN":
        protected |= {"dns", "rdap", "ct_logs"}
    disable = {str(x) for x in out.get("disable_task_types", []) if isinstance(x, str)} - protected
    extra = [str(b)[:200] for b in out.get("additional_search_branches", []) if isinstance(b, str) and b.strip()][:4]
    from eyohe.search.queries import is_query_allowed

    extra = [b for b in extra if is_query_allowed(b)[0]]
    branches = list(plan.branches) + [b for b in extra if b not in plan.branches]
    new_tasks: list[PlannedTask] = []
    for t in plan.tasks:
        enabled = t.enabled and t.task_type not in disable
        params = dict(t.params)
        if t.task_type == "search_web":
            params["branches"] = branches
        new_tasks.append(PlannedTask(t.task_type, t.title, t.rationale, t.category, params, enabled, t.optional))
    rationale = str(out.get("rationale", ""))[:1000] or plan.rationale
    adapted = Plan(
        plan.objective, plan.target_type, plan.target_value, new_tasks, branches, source="ollama", rationale=rationale
    )
    note = f"AI ({client.model}) adapted the plan: {len(extra)} extra search branch(es)" + (
        f", disabled {', '.join(sorted(disable))}" if disable else ""
    )
    return adapted, note
