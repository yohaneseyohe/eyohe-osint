"""Report lifecycle: create record → render in a job → store under DATA_DIR/reports/{case}/ with hash."""

from __future__ import annotations

import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.config import get_settings
from eyohe.core.db import get_session_factory, utcnow
from eyohe.core.enums import AuditAction, ReportFormat
from eyohe.core.errors import NotFoundError
from eyohe.core.ids import next_display_id
from eyohe.core.metrics import report_generation_time
from eyohe.core.security import sha256_bytes
from eyohe.models.auth import User
from eyohe.models.cases import Case
from eyohe.models.reports import Report, ReportSection
from eyohe.reporting.builder import build_report_data
from eyohe.reporting.renderers import render_docx, render_html, render_markdown, render_pdf
from eyohe.services.audit import record_audit

_MIME = {
    "markdown": "text/markdown",
    "html": "text/html",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
_EXT = {"markdown": "md", "html": "html", "pdf": "pdf", "docx": "docx"}


def report_dir(case_id: uuid.UUID) -> Path:
    root = (get_settings().data_dir / "reports").resolve()
    d = (root / str(case_id)).resolve()
    if not d.is_relative_to(root):
        raise ValueError("report path escaped root")
    d.mkdir(parents=True, exist_ok=True)
    return d


async def create_report(
    session: AsyncSession,
    case: Case,
    actor: User,
    *,
    fmt: ReportFormat,
    title: str | None = None,
    classification: str | None = None,
    options: dict[str, Any] | None = None,
) -> Report:
    rep = Report(
        display_id=await next_display_id(session, "report"),
        case_id=case.id,
        title=title or f"{case.name} — Investigation Report",
        format=str(fmt),
        classification=classification or case.classification or get_settings().report_classification,
        status="PENDING",
        generated_by=actor.id,
        options=options or {},
    )
    session.add(rep)
    await session.flush()
    await record_audit(
        session,
        AuditAction.REPORT_GENERATED,
        actor_id=actor.id,
        actor_label=actor.username,
        case_id=case.id,
        object_type="report",
        object_id=rep.display_id,
        detail={"format": str(fmt), "status": "requested"},
    )
    return rep


async def generate_report(report_id: str) -> None:
    """Job entrypoint (embedded or arq)."""
    async with get_session_factory()() as session:
        rep = await session.get(Report, uuid.UUID(report_id))
        if rep is None:
            return
        rep.status = "GENERATING"
        await session.commit()
        t0 = time.perf_counter()
        try:
            actor = await session.get(User, rep.generated_by) if rep.generated_by else None
            data = await build_report_data(session, rep.case_id, analyst=actor, classification=rep.classification)
            out_dir = report_dir(rep.case_id)
            stamp = utcnow().strftime("%Y%m%d-%H%M%S")
            path = out_dir / f"{rep.display_id}-{stamp}.{_EXT[rep.format]}"
            engine = rep.format
            if rep.format == "markdown":
                path.write_text(render_markdown(data), encoding="utf-8")
            elif rep.format == "html":
                path.write_text(render_html(data), encoding="utf-8")
            elif rep.format == "pdf":
                engine = await render_pdf(render_html(data), path)
            elif rep.format == "docx":
                render_docx(data, path)
            content = path.read_bytes()
            rep.file_path = str(path.relative_to(get_settings().data_dir))
            rep.sha256 = sha256_bytes(content)
            rep.size_bytes = len(content)
            rep.status = "READY"
            rep.generated_at = utcnow()
            rep.generation_ms = int((time.perf_counter() - t0) * 1000)
            rep.stats = {**data.stats, "engine": engine}
            # Persist section outline (useful for the UI and for diffing reports later).
            md = render_markdown(data)
            order = 0
            for block in md.split("\n## ")[1:]:
                title, _, body = block.partition("\n")
                import re

                session.add(
                    ReportSection(
                        report_id=rep.id,
                        order=order,
                        key=re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:64],
                        title=title[:256],
                        body_markdown=body[:20000],
                        cited_ids=sorted(set(re.findall(r"EYO-[A-Z]+-\d{6}", body)))[:500],
                    )
                )
                order += 1
            report_generation_time.labels(format=rep.format).observe(time.perf_counter() - t0)
            await record_audit(
                session,
                AuditAction.REPORT_GENERATED,
                actor_id=rep.generated_by,
                actor_label=actor.username if actor else "system",
                case_id=rep.case_id,
                object_type="report",
                object_id=rep.display_id,
                detail={"format": rep.format, "sha256": rep.sha256, "engine": engine},
            )
        except Exception as exc:
            rep.status = "FAILED"
            rep.error = f"{type(exc).__name__}: {getattr(exc, 'message', str(exc))}"[:2000]
        await session.commit()


async def get_report(session: AsyncSession, report_id: uuid.UUID | str) -> Report:
    try:
        rep = await session.get(Report, uuid.UUID(str(report_id)))
    except ValueError:
        rep = (await session.execute(select(Report).where(Report.display_id == str(report_id)))).scalar_one_or_none()
    if rep is None:
        raise NotFoundError("Report not found.")
    return rep


async def list_reports(session: AsyncSession, case_id: uuid.UUID | None = None) -> list[Report]:
    stmt = select(Report)
    if case_id:
        stmt = stmt.where(Report.case_id == case_id)
    return list((await session.execute(stmt.order_by(Report.created_at.desc()))).scalars())


def mime_for(fmt: str) -> str:
    return _MIME.get(fmt, "application/octet-stream")
