from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, status
from fastapi.responses import FileResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from eyohe.api.deps import DB, Analyst, CurrentUser
from eyohe.core.config import get_settings
from eyohe.core.enums import AuditAction, ReportFormat
from eyohe.core.errors import NotFoundError, ValidationError
from eyohe.reporting import exports
from eyohe.reporting import service as report_service
from eyohe.services import cases as case_service
from eyohe.services.audit import record_audit

router = APIRouter(tags=["reports"])


class ReportCreate(BaseModel):
    case_id: uuid.UUID
    format: str = Field(default="pdf", pattern=r"^(markdown|html|pdf|docx)$")
    title: str | None = Field(default=None, max_length=256)
    classification: str | None = Field(default=None, pattern=r"^(INTERNAL|RESEARCH|CONFIDENTIAL)$")


def _out(r: Any) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "display_id": r.display_id,
        "case_id": str(r.case_id),
        "title": r.title,
        "format": r.format,
        "classification": r.classification,
        "status": r.status,
        "file_path": r.file_path,
        "sha256": r.sha256,
        "size_bytes": r.size_bytes,
        "generated_at": r.generated_at,
        "generation_ms": r.generation_ms,
        "stats": r.stats,
        "error": r.error,
        "created_at": r.created_at,
    }


@router.post("/reports", status_code=status.HTTP_202_ACCEPTED)
async def create_report(payload: ReportCreate, user: Analyst, db: DB) -> dict[str, Any]:
    case = await case_service.get_case(db, payload.case_id)
    rep = await report_service.create_report(
        db, case, user, fmt=ReportFormat(payload.format), title=payload.title, classification=payload.classification
    )
    await db.commit()
    from eyohe.orchestrator.jobs import job_manager

    await job_manager.enqueue("generate_report", str(rep.id), key=f"report:{rep.id}")
    return _out(rep)


@router.get("/reports")
async def list_reports(_: CurrentUser, db: DB, case_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    return [_out(r) for r in await report_service.list_reports(db, case_id)]


@router.get("/reports/{report_id}")
async def get_report(report_id: str, _: CurrentUser, db: DB) -> dict[str, Any]:
    rep = await report_service.get_report(db, report_id)
    await db.refresh(rep, attribute_names=["sections"])
    return {**_out(rep), "sections": [{"key": s.key, "title": s.title, "cited_ids": s.cited_ids} for s in rep.sections]}


@router.get("/reports/{report_id}/download")
async def download_report(report_id: str, _: CurrentUser, db: DB) -> FileResponse:
    rep = await report_service.get_report(db, report_id)
    if rep.status != "READY" or not rep.file_path:
        raise NotFoundError(f"Report is not ready (status {rep.status}).")
    root = get_settings().data_dir.resolve()
    path = (root / rep.file_path).resolve()
    if not path.is_relative_to(root) or not path.exists():
        raise NotFoundError("Report file missing.")
    return FileResponse(path, media_type=report_service.mime_for(rep.format), filename=path.name)


@router.get("/reports/{report_id}/preview", response_class=PlainTextResponse)
async def preview_report(report_id: str, _: CurrentUser, db: DB) -> PlainTextResponse:
    rep = await report_service.get_report(db, report_id)
    if rep.status != "READY" or not rep.file_path or rep.format not in ("markdown", "html"):
        raise NotFoundError("Preview is available for ready Markdown/HTML reports only.")
    path = (get_settings().data_dir.resolve() / rep.file_path).resolve()
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type=report_service.mime_for(rep.format))


@router.get("/cases/{case_id}/export")
async def export_case(
    case_id: str, user: CurrentUser, db: DB, format: str = "json", kind: str = "entities"
) -> Response:
    case = await case_service.get_case(db, case_id)
    await record_audit(
        db,
        AuditAction.EXPORT_CREATED,
        actor_id=user.id,
        actor_label=user.username,
        case_id=case.id,
        detail={"format": format, "kind": kind},
    )
    await db.commit()
    base = f"{case.display_id}"
    if format == "json":
        return Response(
            exports.dumps(await exports.export_json(db, case.id)),
            media_type="application/json",
            headers={"content-disposition": f'attachment; filename="{base}.json"'},
        )
    if format == "csv":
        try:
            body = await exports.export_csv(db, case.id, kind)
        except ValueError as exc:
            raise ValidationError("kind must be entities, evidence, sources, relationships or findings") from exc
        return Response(
            body, media_type="text/csv", headers={"content-disposition": f'attachment; filename="{base}-{kind}.csv"'}
        )
    if format == "graphml":
        return Response(
            await exports.export_graphml(db, case.id),
            media_type="application/xml",
            headers={"content-disposition": f'attachment; filename="{base}.graphml"'},
        )
    if format == "markdown":
        from eyohe.reporting.builder import build_report_data
        from eyohe.reporting.renderers import render_markdown

        return Response(
            render_markdown(await build_report_data(db, case.id, analyst=user)),
            media_type="text/markdown",
            headers={"content-disposition": f'attachment; filename="{base}.md"'},
        )
    raise ValidationError("format must be json, csv, graphml or markdown")
