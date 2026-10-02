"""AI analyst endpoints: natural-language queries, intent routing, evidence-only finding drafts."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from eyohe.ai.analyst import answer_question
from eyohe.ai.intents import parse_intent
from eyohe.ai.ollama import OllamaClient
from eyohe.ai.retrieval import case_context, retrieve
from eyohe.ai.summarizer import draft_findings
from eyohe.api.deps import DB, Analyst, CurrentUser
from eyohe.core.enums import AuditAction
from eyohe.services import cases as case_service
from eyohe.services.audit import record_audit

router = APIRouter(prefix="/ai", tags=["ai"])


class AIQuery(BaseModel):
    case_id: uuid.UUID | None = None
    question: str = Field(min_length=1, max_length=2000)
    mode: str = Field(default="auto", pattern=r"^(auto|ask|route)$")


@router.post("/query")
async def ai_query(payload: AIQuery, user: Analyst, db: DB) -> dict[str, Any]:
    """Universal search: structured intent when the request maps to a view; otherwise a cited answer."""
    intent = parse_intent(payload.question, str(payload.case_id) if payload.case_id else None)
    out: dict[str, Any] = {
        "intent": {
            "kind": intent.kind,
            "filters": intent.filters,
            "route": intent.route,
            "explanation": intent.explanation,
        }
    }
    if payload.mode == "route" or (payload.mode == "auto" and intent.kind != "ask"):
        return out
    if payload.case_id is None:
        out["answer"] = {
            "answer": "Select a case to ask questions about its evidence.",
            "citations": [],
            "passages": [],
            "uncited_sentences": [],
            "model": None,
        }
        return out
    case = await case_service.get_case(db, payload.case_id)
    await record_audit(
        db,
        AuditAction.AI_QUERY,
        actor_id=user.id,
        actor_label=user.username,
        case_id=case.id,
        detail={"question": payload.question[:500]},
    )
    await db.commit()
    out["answer"] = await answer_question(db, case.id, payload.question)
    return out


@router.get("/cases/{case_id}/context")
async def ai_context(case_id: str, _: CurrentUser, db: DB) -> dict[str, Any]:
    case = await case_service.get_case(db, case_id)
    return await case_context(db, case.id)


@router.get("/cases/{case_id}/retrieve")
async def ai_retrieve(case_id: str, q: str, _: CurrentUser, db: DB, k: int = 12) -> list[dict[str, Any]]:
    case = await case_service.get_case(db, case_id)
    return [
        {"ref": p.ref, "kind": p.kind, "text": p.text, "score": round(p.score, 3), "meta": p.meta}
        for p in await retrieve(db, case.id, q, k=min(k, 50))
    ]


@router.post("/cases/{case_id}/draft-findings")
async def ai_draft(case_id: str, user: Analyst, db: DB) -> dict[str, Any]:
    case = await case_service.get_case(db, case_id)
    out = await draft_findings(db, case.id)
    await case_service.refresh_counts(db, case.id)
    await db.commit()
    return out


@router.get("/models")
async def ai_models(_: CurrentUser) -> dict[str, Any]:
    client = OllamaClient()
    if not await client.available():
        return {"available": False, "configured": client.model, "models": []}
    models = await client.list_models()
    return {
        "available": True,
        "configured": client.model,
        "models": [
            {
                "name": m.get("name"),
                "size_gb": round((m.get("size") or 0) / 1e9, 1),
                "family": (m.get("details") or {}).get("family"),
                "parameters": (m.get("details") or {}).get("parameter_size"),
            }
            for m in models
        ],
    }
