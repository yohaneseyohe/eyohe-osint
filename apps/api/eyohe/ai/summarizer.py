"""Draft findings strictly from existing evidence.

The model receives evidence records with IDs and must return findings that cite them. Findings
citing unknown IDs are dropped; confidence is computed by the engine, never by the model."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.ai.ollama import OllamaClient
from eyohe.models.evidence import Evidence
from eyohe.models.findings import Finding
from eyohe.models.sources import Source
from eyohe.services import findings as finding_service

_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "claim": {"type": "string"},
                    "assessment": {"type": "string"},
                    "category": {"type": "string"},
                    "supporting": {"type": "array", "items": {"type": "string"}},
                    "contradicting": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "claim", "supporting"],
            },
        }
    },
    "required": ["findings"],
}

SYSTEM = """You write analyst findings for Eyohe OSINT from a list of evidence records.
Rules: every finding must cite one or more evidence IDs (EYO-EV-…) from the list; cite ONLY IDs that appear in the list.
Do not add facts that are not in the evidence. Use neutral language: "DNS records show…", "According to a Reddit post…",
"A Reddit user alleged…", "This may indicate…" for inference. Prefer findings that combine evidence from different sources.
Mark identity/attribution claims with category "identity" and phrase them as possibilities. Produce at most 8 findings.
Categories: infrastructure | organisation | social | historical | identity | document | general."""


async def draft_findings(
    session: AsyncSession, case_id: uuid.UUID, *, investigation_id: uuid.UUID | None = None, limit_evidence: int = 60
) -> dict[str, Any]:
    client = OllamaClient()
    if not await client.available():
        return {"created": 0, "note": "Ollama not reachable; no AI findings drafted", "skipped": True}
    rows = (
        await session.execute(
            select(Evidence, Source)
            .outerjoin(Source, Source.id == Evidence.source_id)
            .where(Evidence.case_id == case_id, Evidence.review_state != "REJECTED")
            .order_by(Evidence.created_at.desc())
            .limit(limit_evidence)
        )
    ).all()
    if not rows:
        return {"created": 0, "note": "no evidence to summarise"}
    existing_titles = {
        f.title.lower() for f in (await session.execute(select(Finding).where(Finding.case_id == case_id))).scalars()
    }
    ev_by_id = {ev.display_id: ev for ev, _ in rows}
    evidence_list = [
        {
            "id": ev.display_id,
            "type": ev.evidence_type,
            "claim": ev.claim[:300],
            "excerpt": ev.excerpt[:200],
            "source": (src.domain if src else ev.collector),
            "tier": src.tier if src else None,
            "collector": ev.collector,
        }
        for ev, src in rows
    ]
    out: dict[str, Any] = await client.chat_json(
        [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": json.dumps(
                    {"evidence": evidence_list, "existing_finding_titles": sorted(existing_titles)[:30]}
                ),
            },
        ],
        schema=_SCHEMA,
        purpose="summarize",
        max_tokens=2500,
    )
    created = 0
    rejected = 0
    ids: list[str] = []
    for item in out.get("findings", [])[:8]:
        sup = [ev_by_id[i].id for i in item.get("supporting", []) if i in ev_by_id]
        con = [ev_by_id[i].id for i in item.get("contradicting", []) if i in ev_by_id]
        title = str(item.get("title", "")).strip()[:512]
        claim = str(item.get("claim", "")).strip()
        if not sup or not title or not claim or title.lower() in existing_titles:
            rejected += 1
            continue
        f = await finding_service.create_finding(
            session,
            case_id,
            title=title,
            claim=claim,
            supporting=sup,
            contradicting=con,
            assessment=str(item.get("assessment", ""))[:2000],
            category=str(item.get("category", "general"))[:32],
            proposed_by="ai",
            investigation_id=investigation_id,
        )
        created += 1
        ids.append(f.display_id)
        existing_titles.add(title.lower())
    await session.flush()
    return {"created": created, "rejected": rejected, "finding_ids": ids}
