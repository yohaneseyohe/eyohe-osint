"""Investigation lifecycle: create → plan → approve → run (pause/resume/stop) → verify → complete."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.config import get_settings
from eyohe.core.db import utcnow
from eyohe.core.enums import AuditAction, CaseStatus, EventType, InvestigationStatus, TargetType, TaskStatus
from eyohe.core.errors import NotFoundError, ValidationError
from eyohe.core.ids import next_display_id
from eyohe.models.auth import User
from eyohe.models.cases import Case, Target
from eyohe.models.investigations import Investigation, InvestigationTask
from eyohe.orchestrator.events import emit_event
from eyohe.orchestrator.planner import Plan, build_template_plan
from eyohe.orchestrator.state import assert_transition
from eyohe.services.audit import record_audit


async def get_investigation(session: AsyncSession, inv_id: uuid.UUID | str) -> Investigation:
    try:
        inv = await session.get(Investigation, uuid.UUID(str(inv_id)))
    except ValueError:
        inv = (
            await session.execute(select(Investigation).where(Investigation.display_id == str(inv_id)))
        ).scalar_one_or_none()
    if inv is None:
        raise NotFoundError(f"Investigation {inv_id} not found.")
    return inv


async def list_investigations(
    session: AsyncSession, case_id: uuid.UUID | None = None, *, status: str | None = None
) -> list[Investigation]:
    stmt = select(Investigation)
    if case_id:
        stmt = stmt.where(Investigation.case_id == case_id)
    if status:
        stmt = stmt.where(Investigation.status == status)
    return list((await session.execute(stmt.order_by(Investigation.created_at.desc()))).scalars())


def _bounds_from_settings(overrides: dict[str, Any] | None) -> dict[str, Any]:
    s = get_settings()
    b = {
        "max_agent_iterations": s.max_agent_iterations,
        "max_research_depth": s.max_research_depth,
        "max_queries": s.max_queries,
        "max_pages": s.max_pages,
        "max_runtime_seconds": s.max_runtime_seconds,
        "max_results_per_source": s.max_results_per_source,
    }
    for k, v in (overrides or {}).items():
        if k in b and isinstance(v, int) and v > 0:
            b[k] = min(v, b[k] * 4)  # analysts can raise bounds but not without limit
    return b


async def create_investigation(
    session: AsyncSession,
    case: Case,
    actor: User,
    *,
    request_text: str,
    target: Target | None = None,
    name: str | None = None,
    bounds: dict[str, Any] | None = None,
) -> Investigation:
    if target is None:
        targets = list(
            (
                await session.execute(
                    select(Target)
                    .where(Target.case_id == case.id)
                    .order_by(Target.is_primary.desc(), Target.created_at)
                )
            ).scalars()
        )
        if not targets:
            raise ValidationError("Add at least one target to the case before starting an investigation.")
        target = targets[0]
    inv = Investigation(
        display_id=await next_display_id(session, "investigation"),
        case_id=case.id,
        name=name or f"Investigate {target.value}",
        request_text=request_text.strip(),
        objective=request_text.strip() or case.objective or f"Investigate {target.value} using public sources.",
        status=InvestigationStatus.DRAFT,
        bounds=_bounds_from_settings(bounds),
        stats={"target_id": str(target.id)},
    )
    session.add(inv)
    await session.flush()
    await record_audit(
        session,
        AuditAction.INVESTIGATION_CREATED,
        actor_id=actor.id,
        actor_label=actor.username,
        case_id=case.id,
        object_type="investigation",
        object_id=inv.display_id,
        detail={"target": target.normalized_value},
    )
    return inv


async def plan_investigation(
    session: AsyncSession, inv: Investigation, actor: User | None, *, use_ai: bool = True
) -> Investigation:
    """Generate the plan (template, optionally adapted by Ollama) and move to AWAITING_APPROVAL."""
    if inv.status != InvestigationStatus.PLANNING:  # background jobs arrive already in PLANNING
        assert_transition(inv.status, InvestigationStatus.PLANNING)
        inv.status = InvestigationStatus.PLANNING
    await session.commit()
    target = await session.get(Target, uuid.UUID(inv.stats["target_id"]))
    if target is None:
        raise NotFoundError("Investigation target no longer exists.")
    await emit_event(
        session, inv, EventType.PLAN, "PLAN", f"Planning investigation for {target.type} {target.normalized_value}"
    )
    plan = build_template_plan(inv.objective, TargetType(target.type), target.normalized_value)
    if use_ai:
        from eyohe.ai.planner import adapt_plan_with_ai
        from eyohe.core.config import get_settings as _gs

        await emit_event(
            session,
            inv,
            EventType.AI_MESSAGE,
            "AI",
            f"Asking {_gs().ollama_model} to adapt the template plan to the objective (this can take a few minutes on CPU)",
        )
        try:
            plan, note = await adapt_plan_with_ai(plan, inv.objective)
            if note:
                await emit_event(session, inv, EventType.AI_MESSAGE, "AI", note)
        except Exception as exc:
            await emit_event(
                session,
                inv,
                EventType.WARNING,
                "AI",
                f"AI plan adaptation unavailable ({type(exc).__name__}); using template plan.",
                level="warning",
            )
    await _apply_plan(session, inv, plan)
    inv.status = InvestigationStatus.AWAITING_APPROVAL
    await emit_event(
        session,
        inv,
        EventType.PLAN,
        "PLAN",
        f"Investigation plan created with {len(plan.tasks)} tasks ({plan.source}); awaiting analyst approval",
        data={"task_count": len(plan.tasks), "source": plan.source},
    )
    return inv


async def plan_investigation_background(investigation_id: str, *, use_ai: bool = True) -> None:
    """Job entrypoint: AI plan adaptation can take minutes on CPU, so planning runs off the request path."""
    from eyohe.core.db import get_session_factory

    async with get_session_factory()() as session:
        inv = await get_investigation(session, investigation_id)
        try:
            await plan_investigation(session, inv, None, use_ai=use_ai)
            await session.commit()
        except Exception as exc:
            await session.rollback()
            inv = await get_investigation(session, investigation_id)
            inv.status = InvestigationStatus.FAILED
            inv.error = f"Planning failed: {type(exc).__name__}: {exc}"[:2000]
            await emit_event(session, inv, EventType.ERROR, "PLAN", inv.error, level="error", commit=False)
            await session.commit()


async def _apply_plan(session: AsyncSession, inv: Investigation, plan: Plan) -> None:
    await session.refresh(inv, attribute_names=["tasks"])
    for t in list(inv.tasks):
        await session.delete(t)
    await session.flush()
    for i, pt in enumerate(plan.tasks):
        session.add(
            InvestigationTask(
                investigation_id=inv.id,
                order=i,
                task_type=pt.task_type,
                title=pt.title,
                rationale=pt.rationale,
                status=TaskStatus.PENDING,
                enabled=pt.enabled,
                params=pt.params,
                category=pt.category,
            )
        )
    inv.plan = plan.to_dict()
    inv.plan_rationale = plan.rationale
    inv.plan_source = plan.source
    await session.flush()
    await session.refresh(inv, attribute_names=["tasks"])


async def update_plan_tasks(
    session: AsyncSession, inv: Investigation, actor: User, changes: list[dict[str, Any]]
) -> Investigation:
    """Analyst enables/disables tasks or edits search branches before approval."""
    if inv.status not in (
        InvestigationStatus.AWAITING_APPROVAL,
        InvestigationStatus.PAUSED,
        InvestigationStatus.STOPPED,
        InvestigationStatus.DRAFT,
    ):
        raise ValidationError("Tasks can only be edited before approval or while paused/stopped.")
    by_id = {str(t.id): t for t in inv.tasks}
    for ch in changes:
        t = by_id.get(str(ch.get("id")))
        if t is None:
            continue
        if "enabled" in ch:
            t.enabled = bool(ch["enabled"])
            if not t.enabled and t.status == TaskStatus.PENDING:
                t.status = TaskStatus.DISABLED
            if t.enabled and t.status == TaskStatus.DISABLED:
                t.status = TaskStatus.PENDING
        if "params" in ch and isinstance(ch["params"], dict):
            t.params = {**t.params, **ch["params"]}
    return inv


async def add_custom_task(
    session: AsyncSession, inv: Investigation, actor: User, task_type: str, params: dict[str, Any], rationale: str
) -> InvestigationTask:
    from eyohe.orchestrator.planner import TASK_CATALOGUE

    if task_type not in TASK_CATALOGUE:
        raise ValidationError(f"Unknown task type '{task_type}'. Allowed: {', '.join(sorted(TASK_CATALOGUE))}.")
    meta = TASK_CATALOGUE[task_type]
    order = max((t.order for t in inv.tasks), default=-1) + 1
    task = InvestigationTask(
        investigation_id=inv.id,
        order=order,
        task_type=task_type,
        title=meta["title"],
        rationale=rationale or f"Added by {actor.username}",
        status=TaskStatus.PENDING,
        enabled=True,
        params=params,
        category=meta["category"],
    )
    session.add(task)
    await session.flush()
    return task


async def approve_and_start(session: AsyncSession, inv: Investigation, actor: User) -> Investigation:
    assert_transition(inv.status, InvestigationStatus.RUNNING)
    await session.refresh(inv, attribute_names=["tasks"])
    if not any(t.enabled for t in inv.tasks):
        raise ValidationError("This investigation has no enabled tasks. Generate or edit the plan before approving it.")
    inv.approved_by = actor.id
    inv.approved_at = utcnow()
    inv.control_flag = None
    inv.error = None
    if inv.started_at is None:
        inv.started_at = utcnow()
    inv.status = InvestigationStatus.RUNNING
    case = await session.get(Case, inv.case_id)
    if case and case.status in (CaseStatus.DRAFT, CaseStatus.PAUSED):
        case.status = CaseStatus.ACTIVE
    await record_audit(
        session,
        AuditAction.INVESTIGATION_APPROVED,
        actor_id=actor.id,
        actor_label=actor.username,
        case_id=inv.case_id,
        object_type="investigation",
        object_id=inv.display_id,
    )
    await emit_event(
        session,
        inv,
        EventType.PLAN_APPROVED,
        "PLAN",
        f"Plan approved by {actor.username}; starting collectors",
        commit=False,
    )
    await session.commit()
    from eyohe.orchestrator.jobs import job_manager

    await job_manager.enqueue("run_investigation", str(inv.id), key=f"inv:{inv.id}")
    return inv


async def request_control(session: AsyncSession, inv: Investigation, actor: User, action: str) -> Investigation:
    """pause | resume | stop. Pause/stop set a cooperative flag the runner honours between tasks."""
    if action == "pause":
        assert_transition(inv.status, InvestigationStatus.PAUSED)
        inv.control_flag = "pause"
        audit = AuditAction.INVESTIGATION_PAUSED
        msg = f"Pause requested by {actor.username}; finishing current task"
    elif action == "stop":
        if inv.status == InvestigationStatus.PAUSED:
            inv.status = InvestigationStatus.STOPPED
            inv.finished_at = utcnow()
        else:
            assert_transition(inv.status, InvestigationStatus.STOPPED)
        inv.control_flag = "stop"
        audit = AuditAction.INVESTIGATION_STOPPED
        msg = f"Stop requested by {actor.username}; state will be persisted"
    elif action == "resume":
        assert_transition(inv.status, InvestigationStatus.RUNNING)
        inv.control_flag = None
        inv.status = InvestigationStatus.RUNNING
        audit = AuditAction.INVESTIGATION_RESUMED
        msg = f"Resumed by {actor.username}; pending tasks will continue"
    else:
        raise ValidationError("action must be pause, resume or stop")
    await record_audit(
        session,
        audit,
        actor_id=actor.id,
        actor_label=actor.username,
        case_id=inv.case_id,
        object_type="investigation",
        object_id=inv.display_id,
    )
    await emit_event(session, inv, EventType.STATUS_CHANGED, "SYSTEM", msg, commit=False)
    await session.commit()
    if action == "resume":
        from eyohe.orchestrator.jobs import job_manager

        await job_manager.enqueue("run_investigation", str(inv.id), key=f"inv:{inv.id}")
    return inv


async def status_summary(session: AsyncSession, inv: Investigation) -> dict[str, Any]:
    """GET INVESTIGATION STATUS: computed from real task/collection state."""
    from eyohe.models.entities import Entity
    from eyohe.models.evidence import Evidence
    from eyohe.models.findings import Finding
    from eyohe.models.sources import Source

    tasks = list(inv.tasks)
    enabled = [t for t in tasks if t.enabled and t.status != TaskStatus.DISABLED]
    done = [t for t in enabled if t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED)]
    failed = [t for t in enabled if t.status == TaskStatus.FAILED]
    active = next((t for t in enabled if t.status == TaskStatus.RUNNING), None)

    async def count(model: Any, *where: Any) -> int:
        return int((await session.execute(select(func.count()).select_from(model).where(*where))).scalar_one())

    ev_n = await count(Evidence, Evidence.investigation_id == inv.id)
    src_n = await count(Source, Source.case_id == inv.case_id)
    ent_n = await count(Entity, Entity.case_id == inv.case_id)
    fnd_n = await count(Finding, Finding.case_id == inv.case_id)
    by_cat: dict[str, dict[str, int]] = {}
    for t in enabled:
        c = by_cat.setdefault(t.category, {"total": 0, "done": 0})
        c["total"] += 1
        if t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED):
            c["done"] += 1
    completeness = {k: round(100 * v["done"] / v["total"]) if v["total"] else 0 for k, v in by_cat.items()}
    overall = round(100 * len(done) / len(enabled)) if enabled else 0
    return {
        "id": str(inv.id),
        "display_id": inv.display_id,
        "status": inv.status,
        "objective": inv.objective,
        "progress": overall,
        "completeness": completeness,
        "active_task": {"id": str(active.id), "title": active.title, "type": active.task_type} if active else None,
        "completed_tasks": [t.title for t in done],
        "failed_tasks": [{"title": t.title, "error": t.error} for t in failed],
        "remaining_tasks": [t.title for t in enabled if t.status == TaskStatus.PENDING],
        "sources_discovered": src_n,
        "entities_discovered": ent_n,
        "evidence_collected": ev_n,
        "findings": fnd_n,
        "warnings": inv.stats.get("warnings", []),
        "errors": [t.error for t in failed if t.error],
        "estimated_remaining_tasks": len([t for t in enabled if t.status == TaskStatus.PENDING]),
        "started_at": inv.started_at.isoformat() if inv.started_at else None,
        "finished_at": inv.finished_at.isoformat() if inv.finished_at else None,
        "plan_source": inv.plan_source,
        "bounds": inv.bounds,
        "stats": inv.stats,
    }
