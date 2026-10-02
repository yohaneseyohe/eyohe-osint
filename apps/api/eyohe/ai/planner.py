"""LLM plan adaptation. The model may only reorder/disable catalogue tasks, add search branches and
write rationale. It cannot invent task types, and the template remains the fallback."""

from __future__ import annotations

from typing import Any

from eyohe.ai.ollama import OllamaClient
from eyohe.orchestrator.planner import TASK_CATALOGUE, Plan, PlannedTask

_SCHEMA = {
    "type": "object",
    "properties": {
        "rationale": {"type": "string"},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "task_type": {"type": "string"},
                    "enabled": {"type": "boolean"},
                    "rationale": {"type": "string"},
                },
                "required": ["task_type", "enabled", "rationale"],
            },
        },
        "additional_search_branches": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["rationale", "tasks"],
}

SYSTEM = (
    "You are the planning component of Eyohe OSINT, a public-source intelligence workstation. "
    "You adapt an investigation plan. Rules: use ONLY the provided task types; never invent facts about "
    "the target; keep technical tasks (dns, rdap, ct_logs) enabled for domains; keep 'verify' enabled; "
    "explain each task in one sentence tied to the analyst's objective; propose at most 6 additional "
    "search queries using operators like site:, intitle:, filetype:, quotes. Public sources only; never "
    "propose bypassing authentication, paywalls or anti-bot controls."
)


async def adapt_plan_with_ai(plan: Plan, objective: str) -> tuple[Plan, str]:
    client = OllamaClient()
    if not await client.available():
        return plan, ""
    catalogue = {k: v["title"] for k, v in TASK_CATALOGUE.items()}
    user = {
        "objective": objective,
        "target_type": plan.target_type,
        "target_value": plan.target_value,
        "available_task_types": catalogue,
        "template_tasks": [
            {"task_type": t.task_type, "enabled": t.enabled, "rationale": t.rationale} for t in plan.tasks
        ],
        "template_search_branches": plan.branches,
    }
    import json

    out: dict[str, Any] = await client.chat_json(
        [{"role": "system", "content": SYSTEM}, {"role": "user", "content": json.dumps(user)}],
        schema=_SCHEMA,
        purpose="plan",
        max_tokens=1500,
    )
    allowed = set(TASK_CATALOGUE)
    by_type = {t.task_type: t for t in plan.tasks}
    new_tasks: list[PlannedTask] = []
    seen: set[str] = set()
    for item in out.get("tasks", []):
        tt = str(item.get("task_type", ""))
        if tt not in allowed or tt in seen:
            continue
        seen.add(tt)
        base = by_type.get(tt)
        meta = TASK_CATALOGUE[tt]
        enabled = bool(item.get("enabled", True))
        if tt in ("verify", "correlate"):
            enabled = True
        rationale = str(item.get("rationale") or (base.rationale if base else ""))[:500]
        new_tasks.append(
            PlannedTask(
                tt,
                meta["title"],
                rationale,
                meta["category"],
                dict(base.params) if base else {},
                enabled,
                base.optional if base else True,
            )
        )
    # Keep any template task the model dropped (disabled rather than deleted so the analyst sees it).
    for t in plan.tasks:
        if t.task_type not in seen:
            new_tasks.append(
                PlannedTask(
                    t.task_type,
                    t.title,
                    t.rationale,
                    t.category,
                    dict(t.params),
                    t.enabled if t.task_type in ("verify", "correlate") else False,
                    t.optional,
                )
            )
    extra = [str(b)[:200] for b in out.get("additional_search_branches", []) if isinstance(b, str) and b.strip()][:6]
    branches = list(plan.branches) + [b for b in extra if b not in plan.branches]
    for t in new_tasks:
        if t.task_type == "search_web":
            t.params["branches"] = branches
    # Ensure verification tasks run last.
    tail = [t for t in new_tasks if t.task_type in ("correlate", "verify", "summarize")]
    head = [t for t in new_tasks if t.task_type not in ("correlate", "verify", "summarize")]
    adapted = Plan(
        plan.objective,
        plan.target_type,
        plan.target_value,
        head + tail,
        branches,
        source="ollama",
        rationale=str(out.get("rationale", ""))[:2000] or plan.rationale,
    )
    return (
        adapted,
        f"AI ({client.model}) adapted the plan: {len(head)} collection tasks, {len(extra)} extra search branches",
    )
