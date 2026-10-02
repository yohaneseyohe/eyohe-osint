"""Search playground + per-case query history."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from eyohe.api.deps import DB, Analyst, CurrentUser
from eyohe.core.enums import EvidenceType, TargetType
from eyohe.core.errors import NotFoundError
from eyohe.enrichment.extract import extract_entities
from eyohe.search import service as search_service
from eyohe.search.providers import PROVIDERS, provider_health
from eyohe.search.providers import search as run_search
from eyohe.search.queries import generate_branches, is_query_allowed
from eyohe.services import cases as case_service
from eyohe.services import evidence as ev_service

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=400)
    category: str = Field(default="general", pattern=r"^(general|news|code|social|documents)$")
    max_results: int = Field(default=20, ge=1, le=50)
    providers: list[str] | None = None
    case_id: uuid.UUID | None = Field(
        default=None, description="When set, the query and results are stored on the case"
    )


@router.get("/providers")
async def providers(_: CurrentUser) -> dict[str, Any]:
    h = await provider_health()
    return {
        "health": {"status": h.status, "message": h.message, **h.detail},
        "providers": [
            {
                "name": p.name,
                "configured": p.configured()[0],
                "note": p.configured()[1] if not p.configured()[0] else "",
            }
            for p in PROVIDERS.values()
        ],
    }


@router.post("/branches")
async def branches(payload: dict[str, str], _: CurrentUser) -> list[dict[str, str]]:
    from eyohe.enrichment.classify import classify_target

    ttype, norm, _extra = classify_target(payload.get("value", ""))
    if payload.get("type"):
        ttype = TargetType(payload["type"])
    return [
        {"name": b.name, "query": b.query, "category": b.category}
        for b in generate_branches(ttype, norm, objective=payload.get("objective", ""))
    ]


@router.post("")
async def search(payload: SearchRequest, user: Analyst, db: DB) -> dict[str, Any]:
    ok, why = is_query_allowed(payload.query)
    if not ok:
        from eyohe.core.errors import ValidationError

        raise ValidationError(why)
    if payload.case_id:
        case = await case_service.get_case(db, payload.case_id)
        sq, rows, resp = await search_service.execute_and_store(
            db,
            case.id,
            query=payload.query,
            category=payload.category,
            max_results=payload.max_results,
            providers=payload.providers,
            actor_label=user.username,
            branch="playground",
        )
        await db.commit()
        return {
            "query_id": str(sq.id),
            "provider": sq.provider,
            "cache_hit": sq.cache_hit,
            "elapsed_ms": resp.elapsed_ms if resp else None,
            "warnings": resp.warnings if resp else [],
            "results": [
                {
                    **search_service.result_to_dict(r),
                    "entities": [
                        {"type": e.type, "value": e.value}
                        for e in extract_entities(f"{r.title} {r.snippet} {r.url}")[:8]
                    ],
                }
                for r in rows
            ],
        }
    resp = await run_search(
        payload.query, category=payload.category, max_results=payload.max_results, providers=payload.providers
    )
    return {
        "query_id": None,
        "provider": resp.provider,
        "cache_hit": resp.cache_hit,
        "elapsed_ms": resp.elapsed_ms,
        "warnings": resp.warnings,
        "results": [
            {
                "id": None,
                "rank": i + 1,
                "title": h.title,
                "url": h.url,
                "canonical_url": h.canonical_url,
                "domain": h.domain,
                "snippet": h.snippet,
                "published_at": h.published_at,
                "engine": h.engine,
                "relevance": h.score,
                "status": "NEW",
                "source_id": None,
                "entities": [
                    {"type": e.type, "value": e.value} for e in extract_entities(f"{h.title} {h.snippet} {h.url}")[:8]
                ],
            }
            for i, h in enumerate(resp.hits)
        ],
    }


@router.get("/cases/{case_id}/queries")
async def case_queries(
    case_id: str, _: CurrentUser, db: DB, investigation_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    case = await case_service.get_case(db, case_id)
    return [
        {
            "id": str(q.id),
            "branch": q.branch,
            "query": q.query,
            "provider": q.provider,
            "status": q.status,
            "enabled": q.enabled,
            "result_count": q.result_count,
            "error": q.error,
            "executed_at": q.executed_at,
            "cache_hit": q.cache_hit,
            "created_at": q.created_at,
        }
        for q in await search_service.list_queries(db, case.id, investigation_id)
    ]


@router.get("/cases/{case_id}/results")
async def case_results(
    case_id: str,
    _: CurrentUser,
    db: DB,
    query_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = Query(200, le=1000),
) -> list[dict[str, Any]]:
    case = await case_service.get_case(db, case_id)
    return [
        search_service.result_to_dict(r)
        for r in await search_service.list_results(db, case.id, query_id=query_id, status=status, limit=limit)
    ]


class ResultAction(BaseModel):
    action: str = Field(pattern=r"^(save|ignore|add_evidence|investigate)$")
    claim: str | None = None


@router.post("/results/{result_id}")
async def result_action(result_id: uuid.UUID, payload: ResultAction, user: Analyst, db: DB) -> dict[str, Any]:
    from eyohe.models.investigations import SearchResult

    row = await db.get(SearchResult, result_id)
    if row is None:
        raise NotFoundError("Search result not found.")
    out: dict[str, Any] = {"result_id": str(row.id), "action": payload.action}
    if payload.action == "ignore":
        row.status = "IGNORED"
    elif payload.action in ("save", "add_evidence"):
        st, tier, note = search_service.classify_hit(row.domain, "general")
        src = await ev_service.upsert_source(
            db,
            row.case_id,
            url=row.url,
            source_type=st,
            collector="analyst",
            tier=tier,
            title=row.title,
            published_at=row.published_at,
            reliability_note=note,
            metadata={"engine": row.engine, "saved_by": user.username},
        )
        row.source_id = src.id
        row.status = "SAVED"
        out["source_id"] = str(src.id)
        if payload.action == "add_evidence":
            ev = await ev_service.create_evidence(
                db,
                row.case_id,
                claim=payload.claim or f"Public page '{row.title}' references the target",
                evidence_type=EvidenceType.TECHNICAL_RECORD,
                collector="analyst",
                source=src,
                excerpt=row.snippet[:1000],
                collection_method=f"playground:{user.username}",
            )
            out["evidence_id"] = str(ev.id)
            out["evidence_display_id"] = ev.display_id
    elif payload.action == "investigate":
        case = await case_service.get_case(db, row.case_id)
        try:
            t = await case_service.add_target(db, case, row.url, actor=user, label=row.title[:200])
            out["target_id"] = str(t.id)
        except Exception as exc:
            out["note"] = getattr(exc, "message", str(exc))
    await db.commit()
    return out
