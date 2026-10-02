"""Monitors: scheduled re-collection with baseline comparison → alerts.

Checks: dns, ct (certificates/subdomains), search (new public pages), github, reddit, news.
A monitor stores a compact baseline (record sets, URLs) and raises typed alerts for differences.
Every alert links to the evidence created for the new observation."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.collectors.base import CollectContext
from eyohe.collectors.registry import collector_registry
from eyohe.core.db import get_session_factory, utcnow
from eyohe.core.enums import AlertType, AuditAction, EventType, InvestigationStatus, TargetType
from eyohe.core.errors import NotFoundError, ValidationError
from eyohe.core.ids import next_display_id
from eyohe.core.logging import get_logger
from eyohe.models.auth import User
from eyohe.models.cases import Case, Target
from eyohe.models.investigations import Investigation
from eyohe.models.monitoring import Alert, Monitor
from eyohe.orchestrator.persist import persist_result
from eyohe.scheduler.notify import deliver
from eyohe.services.audit import record_audit

log = get_logger("monitors")
SCHEDULES = {"hourly": timedelta(hours=1), "daily": timedelta(days=1), "weekly": timedelta(weeks=1)}
CHECKS = ("dns", "ct", "search", "github", "reddit", "news")


def next_run(schedule: str, after: Any = None) -> Any:
    after = after or utcnow()
    if schedule in SCHEDULES:
        return after + SCHEDULES[schedule]
    if croniter.is_valid(schedule):
        return croniter(schedule, after).get_next(ret_type=type(after))
    raise ValidationError("schedule must be hourly, daily, weekly or a cron expression")


async def create_monitor(
    session: AsyncSession,
    case: Case,
    actor: User,
    *,
    name: str,
    target_value: str,
    target_type: str,
    checks: list[str],
    schedule: str = "daily",
    keywords: list[str] | None = None,
    notify: dict[str, Any] | None = None,
    target_id: uuid.UUID | None = None,
) -> Monitor:
    bad = [c for c in checks if c not in CHECKS]
    if bad or not checks:
        raise ValidationError(f"checks must be a non-empty subset of {', '.join(CHECKS)}")
    mon = Monitor(
        display_id=await next_display_id(session, "monitor"),
        case_id=case.id,
        target_id=target_id,
        name=name[:256],
        target_value=target_value,
        target_type=target_type,
        checks=checks,
        schedule=schedule,
        keywords=keywords or [],
        notify=notify or {},
        next_run_at=next_run(schedule),
    )
    session.add(mon)
    await session.flush()
    await record_audit(
        session,
        AuditAction.MONITOR_CREATED,
        actor_id=actor.id,
        actor_label=actor.username,
        case_id=case.id,
        object_type="monitor",
        object_id=mon.display_id,
        detail={"checks": checks, "schedule": schedule},
    )
    return mon


async def get_monitor(session: AsyncSession, monitor_id: uuid.UUID | str) -> Monitor:
    try:
        m = await session.get(Monitor, uuid.UUID(str(monitor_id)))
    except ValueError:
        m = (await session.execute(select(Monitor).where(Monitor.display_id == str(monitor_id)))).scalar_one_or_none()
    if m is None:
        raise NotFoundError("Monitor not found.")
    return m


async def run_due_monitors() -> int:
    now = utcnow()
    async with get_session_factory()() as session:
        due = list(
            (
                await session.execute(select(Monitor.id).where(Monitor.enabled.is_(True), Monitor.next_run_at <= now))
            ).scalars()
        )
    for mid in due:
        try:
            await run_monitor(str(mid))
        except Exception as exc:
            log.warning("monitor_run_failed", monitor=str(mid), error=str(exc)[:200])
    return len(due)


async def _monitor_investigation(session: AsyncSession, mon: Monitor) -> Investigation:
    """Monitor runs persist through a dedicated, re-used investigation so provenance/events exist."""
    inv = (
        await session.execute(
            select(Investigation).where(
                Investigation.case_id == mon.case_id, Investigation.name == f"Monitor {mon.display_id}"
            )
        )
    ).scalar_one_or_none()
    if inv is None:
        from eyohe.core.ids import next_display_id as nid

        target = await session.get(Target, mon.target_id) if mon.target_id else None
        inv = Investigation(
            display_id=await nid(session, "investigation"),
            case_id=mon.case_id,
            name=f"Monitor {mon.display_id}",
            request_text=f"Scheduled monitoring of {mon.target_value}",
            objective=f"Detect public changes for {mon.target_value}",
            status=InvestigationStatus.COMPLETED,
            plan_source="monitor",
            stats={"target_id": str(target.id) if target else "", "monitor": mon.display_id},
        )
        session.add(inv)
        await session.flush()
    return inv


async def run_monitor(monitor_id: str) -> dict[str, Any]:
    async with get_session_factory()() as session:
        mon = await get_monitor(session, monitor_id)
        case = await session.get(Case, mon.case_id)
        inv = await _monitor_investigation(session, mon)
        ttype = TargetType(mon.target_type)
        baseline: dict[str, Any] = dict(mon.baseline or {})
        first_run = not baseline
        alerts: list[Alert] = []
        errors: list[str] = []
        from eyohe.orchestrator.events import emit_event

        await emit_event(
            session, inv, EventType.INFO, "MONITOR", f"Monitor {mon.display_id} run started ({', '.join(mon.checks)})"
        )
        for check in mon.checks:
            try:
                observed = await _observe(session, inv, mon, check, ttype)
            except Exception as exc:
                msg = getattr(exc, "message", str(exc))[:300]
                errors.append(f"{check}: {msg}")
                await session.rollback()
                mon = await get_monitor(session, monitor_id)
                inv = await _monitor_investigation(session, mon)
                alerts.append(
                    await _alert(session, mon, AlertType.MONITOR_ERROR, "WARNING", f"{check} check failed", msg, check)
                )
                continue
            prev = baseline.get(check)
            if prev is not None:
                for a in _diff(check, prev, observed):
                    alerts.append(
                        await _alert(
                            session,
                            mon,
                            a["type"],
                            a.get("severity", "INFO"),
                            a["title"],
                            a["message"],
                            check,
                            a.get("data"),
                        )
                    )
            baseline[check] = observed
            # Keyword matches on anything new
            if mon.keywords and observed.get("texts"):
                for kw in mon.keywords:
                    hits = [t for t in observed["texts"] if kw.lower() in t.lower()]
                    new_hits = [h for h in hits if h not in (prev or {}).get("texts", [])] if prev else hits
                    if new_hits and not first_run:
                        alerts.append(
                            await _alert(
                                session,
                                mon,
                                AlertType.KEYWORD_MATCH,
                                "INFO",
                                f"Keyword '{kw}' matched in {check}",
                                "\n".join(new_hits[:5])[:1500],
                                check,
                            )
                        )
        for key in list(baseline):
            if "texts" in baseline[key]:
                baseline[key]["texts"] = baseline[key]["texts"][:200]
        mon.baseline = baseline
        mon.last_run_at = utcnow()
        mon.run_count += 1
        mon.next_run_at = next_run(mon.schedule, mon.last_run_at)
        mon.last_status = "ERROR" if errors and len(errors) == len(mon.checks) else ("PARTIAL" if errors else "OK")
        mon.last_error = "; ".join(errors)[:2000] if errors else None
        await record_audit(
            session,
            AuditAction.MONITOR_RUN,
            case_id=mon.case_id,
            object_type="monitor",
            object_id=mon.display_id,
            detail={"alerts": len(alerts), "errors": errors[:5], "first_run": first_run},
        )
        await emit_event(
            session,
            inv,
            EventType.INFO,
            "MONITOR",
            f"Monitor run finished: {len(alerts)} alert(s)"
            + (" (baseline established)" if first_run else "")
            + (f", errors: {len(errors)}" if errors else ""),
            commit=False,
        )
        await session.commit()
        for al in alerts:
            delivered = await deliver(
                {
                    "alert_type": al.alert_type,
                    "title": al.title,
                    "message": al.message,
                    "case_display_id": case.display_id if case else "",
                    "monitor": mon.display_id,
                    "detected": al.created_at.isoformat(),
                },
                mon.notify,
            )
            al.delivered = delivered
        await session.commit()
        return {"alerts": len(alerts), "errors": errors, "first_run": first_run, "status": mon.last_status}


async def _observe(
    session: AsyncSession, inv: Investigation, mon: Monitor, check: str, ttype: TargetType
) -> dict[str, Any]:
    ctx = CollectContext(case_id=str(mon.case_id), investigation_id=str(inv.id), max_results=15)
    if check == "dns":
        res = await _collect(ctx, "dns", TargetType.DOMAIN, mon.target_value.split("@")[-1])
        await persist_result(session, inv, None, res, emit=False)
        recs = {}
        for ev in res.evidence:
            recs[ev.structured.get("record_type", "?")] = sorted(ev.structured.get("values", []))
        return {"records": recs}
    if check == "ct":
        res = await _collect(ctx, "ct_logs", TargetType.DOMAIN, mon.target_value)
        await persist_result(session, inv, None, res, emit=False)
        subs = res.evidence[0].structured.get("subdomains", []) if res.evidence else []
        return {"subdomains": sorted(subs), "certificates": res.summary.get("records", 0)}
    if check in ("github", "reddit"):
        res = await _collect(ctx, check, ttype, mon.target_value)
        await persist_result(session, inv, None, res, emit=False)
        urls = sorted({s.url for s in res.sources})
        return {"urls": urls, "texts": [f"{s.title} {s.url}" for s in res.sources][:200]}
    if check in ("search", "news"):
        from eyohe.search.providers import search

        q = f'"{mon.target_value}"' if " " in mon.target_value or "." in mon.target_value else mon.target_value
        resp = await search(q, category="news" if check == "news" else "general", max_results=20, use_cache=False)
        from eyohe.collectors.base import CollectResult, SourceItem
        from eyohe.search.service import classify_hit

        res = CollectResult(collector=f"monitor/{check}")
        for h in resp.hits:
            st, tier, note = classify_hit(
                h.domain,
                "news" if check == "news" else "general",
                mon.target_value if ttype == TargetType.DOMAIN else None,
            )
            res.sources.append(
                SourceItem(
                    url=h.url,
                    source_type=st,
                    title=h.title,
                    published_at=h.published_at,
                    tier=tier,
                    reliability_note=note,
                    metadata={"query": q, "engine": h.engine},
                )
            )
        await persist_result(session, inv, None, res, emit=False)
        return {
            "urls": sorted(h.canonical_url for h in resp.hits),
            "texts": [f"{h.title} {h.snippet[:160]} {h.url}" for h in resp.hits][:200],
        }
    raise ValidationError(f"unknown check {check}")


async def _collect(ctx: CollectContext, name: str, ttype: TargetType, value: str) -> Any:
    col = collector_registry.get(name)
    if col is None:
        from eyohe.core.errors import ConfigurationError

        raise ConfigurationError(f"collector {name} unavailable")
    return await col.collect(ctx, ttype, value)


def _diff(check: str, prev: dict[str, Any], cur: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if check == "dns":
        for rt in sorted(set(prev.get("records", {})) | set(cur.get("records", {}))):
            a, b = set(prev.get("records", {}).get(rt, [])), set(cur.get("records", {}).get(rt, []))
            if a != b:
                out.append(
                    {
                        "type": AlertType.DOMAIN_CHANGE,
                        "severity": "WARNING" if rt in ("A", "AAAA", "NS", "MX") else "INFO",
                        "title": f"DNS {rt} records changed",
                        "message": f"added: {sorted(b - a) or '—'}\nremoved: {sorted(a - b) or '—'}",
                        "data": {"record_type": rt, "added": sorted(b - a), "removed": sorted(a - b)},
                    }
                )
    elif check == "ct":
        new = sorted(set(cur.get("subdomains", [])) - set(prev.get("subdomains", [])))
        if new:
            out.append(
                {
                    "type": AlertType.CERTIFICATE_CHANGE,
                    "severity": "INFO",
                    "title": f"{len(new)} new hostname(s) in certificate transparency",
                    "message": "\n".join(new[:20]),
                    "data": {"new": new[:100]},
                }
            )
    else:
        new = sorted(set(cur.get("urls", [])) - set(prev.get("urls", [])))
        if new:
            out.append(
                {
                    "type": AlertType.NEW_SOURCE,
                    "severity": "INFO",
                    "title": f"{len(new)} new public {check} result(s)",
                    "message": "\n".join(new[:20]),
                    "data": {"new": new[:100]},
                }
            )
    return out


async def _alert(
    session: AsyncSession,
    mon: Monitor,
    atype: str,
    severity: str,
    title: str,
    message: str,
    source_label: str,
    data: dict[str, Any] | None = None,
) -> Alert:
    a = Alert(
        display_id=await next_display_id(session, "alert"),
        case_id=mon.case_id,
        monitor_id=mon.id,
        alert_type=str(atype),
        severity=severity,
        title=title[:512],
        message=message[:4000],
        source_label=source_label,
        data=data or {},
    )
    session.add(a)
    await session.flush()
    await record_audit(
        session,
        AuditAction.ALERT_CREATED,
        case_id=mon.case_id,
        object_type="alert",
        object_id=a.display_id,
        detail={"type": str(atype), "monitor": mon.display_id},
    )
    return a
