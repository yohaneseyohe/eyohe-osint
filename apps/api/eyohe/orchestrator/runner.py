"""Investigation runner: executes planned tasks in order with cooperative pause/stop, bounds, and
per-task persistence so a stopped investigation can resume exactly where it left off."""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.db import get_session_factory, utcnow
from eyohe.core.enums import CaseStatus, EventType, InvestigationStatus, TaskStatus
from eyohe.core.errors import CollectorError, ConfigurationError
from eyohe.core.logging import get_logger
from eyohe.core.metrics import collector_errors, investigations_active, investigations_total
from eyohe.models.cases import Case, Target
from eyohe.models.investigations import Investigation, InvestigationTask
from eyohe.orchestrator.events import emit_event
from eyohe.orchestrator.executors import RunContext, get_executor
from eyohe.services.cases import refresh_counts

log = get_logger("runner")


async def _load(session: AsyncSession, inv_id: uuid.UUID) -> Investigation:
    inv = (await session.execute(select(Investigation).where(Investigation.id == inv_id))).scalar_one()
    await session.refresh(inv, attribute_names=["tasks"])
    return inv


async def _control(session: AsyncSession, inv_id: uuid.UUID) -> str | None:
    """Re-read the control flag from the DB so API requests can pause/stop a running job."""
    row = await session.execute(
        select(Investigation.control_flag, Investigation.status).where(Investigation.id == inv_id)
    )
    flag, status = row.one()
    if status == InvestigationStatus.STOPPED:
        return "stop"
    return flag


async def run_investigation(investigation_id: str) -> None:
    inv_id = uuid.UUID(investigation_id)
    factory = get_session_factory()
    investigations_total.inc()
    investigations_active.inc()
    started = time.monotonic()
    try:
        async with factory() as session:
            inv = await _load(session, inv_id)
            if inv.status != InvestigationStatus.RUNNING:
                log.info("runner_skip", investigation=inv.display_id, status=inv.status)
                return
            target = await session.get(Target, uuid.UUID(inv.stats["target_id"]))
            case = await session.get(Case, inv.case_id)
            if target is None or case is None:
                inv.status = InvestigationStatus.FAILED
                inv.error = "Target or case missing"
                await session.commit()
                return
            ctx = RunContext(session=session, investigation=inv, case=case, target=target, bounds=dict(inv.bounds))
            max_runtime = int(inv.bounds.get("max_runtime_seconds", 1800))

            for task in sorted(inv.tasks, key=lambda t: t.order):
                if not task.enabled or task.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED, TaskStatus.DISABLED):
                    continue
                flag = await _control(session, inv_id)
                if flag == "pause":
                    inv.status = InvestigationStatus.PAUSED
                    inv.control_flag = None
                    await emit_event(
                        session,
                        inv,
                        EventType.STATUS_CHANGED,
                        "SYSTEM",
                        "Investigation paused; state persisted",
                        commit=False,
                    )
                    await session.commit()
                    return
                if flag == "stop":
                    await _finish(
                        session, inv, InvestigationStatus.STOPPED, "Investigation stopped by analyst; state persisted"
                    )
                    return
                if time.monotonic() - started > max_runtime:
                    inv.stats = {
                        **inv.stats,
                        "warnings": [*inv.stats.get("warnings", []), f"MAX_RUNTIME_SECONDS ({max_runtime}s) reached"],
                    }
                    await emit_event(
                        session,
                        inv,
                        EventType.WARNING,
                        "SYSTEM",
                        f"Runtime bound reached ({max_runtime}s); remaining tasks left pending",
                        level="warning",
                        commit=False,
                    )
                    break
                await _run_task(ctx, task)
                await session.commit()

            inv = await _load(session, inv_id)
            pending = [t for t in inv.tasks if t.enabled and t.status == TaskStatus.PENDING]
            if pending:
                await _finish(
                    session,
                    inv,
                    InvestigationStatus.STOPPED,
                    f"Stopped with {len(pending)} task(s) pending (resumable)",
                )
                return
            inv.status = InvestigationStatus.VERIFYING
            await emit_event(
                session,
                inv,
                EventType.VERIFICATION_STARTED,
                "VERIFY",
                "Final verification pass: recomputing confidence from evidence",
            )
            from eyohe.verification.service import verify_case

            summary = await verify_case(session, inv.case_id, inv)
            await emit_event(
                session,
                inv,
                EventType.VERIFICATION_COMPLETED,
                "VERIFY",
                f"Verification complete: {summary.get('findings', 0)} findings, "
                f"{summary.get('contradictions', 0)} contradictions",
                data=summary,
                commit=False,
            )
            await _finish(session, inv, InvestigationStatus.COMPLETED, "Investigation completed")
    except asyncio.CancelledError:
        async with factory() as session:
            inv = await _load(session, inv_id)
            if inv.status == InvestigationStatus.RUNNING:
                await _finish(session, inv, InvestigationStatus.STOPPED, "Runner cancelled (shutdown); state persisted")
        raise
    except Exception as exc:
        log.exception("runner_failed", investigation=investigation_id)
        async with factory() as session:
            inv = await _load(session, inv_id)
            inv.error = f"{type(exc).__name__}: {exc}"[:2000]
            await _finish(session, inv, InvestigationStatus.FAILED, f"Investigation failed: {inv.error}", level="error")
    finally:
        investigations_active.dec()


async def _finish(
    session: AsyncSession, inv: Investigation, status: InvestigationStatus, message: str, level: str = "info"
) -> None:
    inv.status = status
    inv.control_flag = None
    inv.finished_at = utcnow()
    await refresh_counts(session, inv.case_id)
    case = await session.get(Case, inv.case_id)
    if case and status == InvestigationStatus.COMPLETED and case.status == CaseStatus.ACTIVE:
        pass  # case stays ACTIVE; analysts close cases explicitly
    await emit_event(
        session, inv, EventType.STATUS_CHANGED, "SYSTEM", message, level=level, data={"status": status}, commit=False
    )
    await session.commit()


async def _run_task(ctx: RunContext, task: InvestigationTask) -> None:
    session, inv = ctx.session, ctx.investigation
    task.status = TaskStatus.RUNNING
    task.attempts += 1
    task.started_at = utcnow()
    task.error = None
    await emit_event(
        session,
        inv,
        EventType.TASK_STARTED,
        _stage_for(task.task_type),
        f"{task.title} started",
        task_id=task.id,
        data={"task_type": task.task_type, "rationale": task.rationale},
        commit=False,
    )
    await session.commit()
    executor = get_executor(task.task_type)
    t0 = time.monotonic()
    try:
        if executor is None:
            task.status = TaskStatus.SKIPPED
            task.result_summary = {"reason": "no executor registered for this task type in this build"}
            await emit_event(
                session,
                inv,
                EventType.TASK_SKIPPED,
                _stage_for(task.task_type),
                f"{task.title} skipped: not available",
                level="warning",
                task_id=task.id,
                commit=False,
            )
            return
        summary: dict[str, Any] = await asyncio.wait_for(
            executor(ctx, task), timeout=max(60, int(ctx.bounds.get("max_runtime_seconds", 1800)) // 2)
        )
        task.status = TaskStatus.COMPLETED
        task.result_summary = summary
        await emit_event(
            session,
            inv,
            EventType.TASK_COMPLETED,
            _stage_for(task.task_type),
            _summary_line(task.title, summary),
            task_id=task.id,
            data={**summary, "ms": int((time.monotonic() - t0) * 1000)},
            commit=False,
        )
    except ConfigurationError as exc:
        task.status = TaskStatus.SKIPPED
        task.error = exc.message
        task.result_summary = {"reason": exc.message, "not_configured": True}
        await emit_event(
            session,
            inv,
            EventType.TASK_SKIPPED,
            _stage_for(task.task_type),
            f"{task.title} skipped: {exc.message}",
            level="warning",
            task_id=task.id,
            data=exc.detail,
            commit=False,
        )
    except (CollectorError, TimeoutError, Exception) as exc:
        await session.rollback()
        task = await session.get(InvestigationTask, task.id) or task
        task.status = TaskStatus.FAILED
        if isinstance(exc, TimeoutError):
            task.error = "Task timed out"
        else:
            task.error = getattr(exc, "message", None) or f"{type(exc).__name__}: {exc}"
        task.error = task.error[:2000]
        collector_errors.labels(collector=task.task_type).inc()
        detail = getattr(exc, "detail", {}) or {}
        await emit_event(
            session,
            inv,
            EventType.TASK_FAILED,
            _stage_for(task.task_type),
            f"{task.title} failed: {task.error}",
            level="error",
            task_id=task.id,
            data={**detail, "retry": "resume the investigation to retry failed tasks"},
            commit=False,
        )
    finally:
        task.finished_at = utcnow()


def _summary_line(title: str, s: dict[str, Any]) -> str:
    parts = []
    for k in ("sources", "evidence", "entities", "relationships", "results", "records", "snapshots", "findings"):
        if s.get(k):
            parts.append(f"{s[k]} {k}")
    return (
        f"{title}: {', '.join(parts)}" if parts else f"{title} completed: {s.get('note', 'no new public data found')}"
    )


def _stage_for(task_type: str) -> str:
    from eyohe.orchestrator.planner import TASK_CATALOGUE

    return TASK_CATALOGUE.get(task_type, {}).get("stage", task_type.upper()[:12])
