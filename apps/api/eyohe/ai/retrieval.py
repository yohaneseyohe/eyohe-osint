"""Case-level retrieval for the AI analyst (RAG).

PostgreSQL full-text search when available, LIKE-based keyword matching on SQLite. Only the
top-k passages (evidence, findings, notes, snapshot excerpts) are sent to the model, each tagged
with its display ID so answers can cite them."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.config import get_settings
from eyohe.models.cases import Note
from eyohe.models.entities import Entity
from eyohe.models.evidence import Evidence
from eyohe.models.findings import Finding
from eyohe.models.sources import Source, SourceSnapshot

_STOP = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "what",
    "which",
    "show",
    "find",
    "all",
    "are",
    "any",
    "from",
    "about",
    "does",
    "did",
    "who",
    "how",
    "evidence",
    "sources",
    "source",
    "mention",
    "mentions",
    "related",
    "to",
    "of",
    "in",
    "on",
    "a",
    "an",
    "is",
    "me",
    "give",
    "list",
}


@dataclass
class Passage:
    ref: str  # display id (EYO-EV-… / EYO-FND-… / note:<uuid> / EYO-SRC-…)
    kind: str
    text: str
    score: float
    meta: dict[str, Any]


def keywords(question: str) -> list[str]:
    toks = re.findall(r"[A-Za-z0-9@._:/-]{3,}", question.lower())
    out = []
    for t in toks:
        t = t.strip(".:/,")
        if t and t not in _STOP and t not in out:
            out.append(t)
    return out[:8]


async def retrieve(session: AsyncSession, case_id: uuid.UUID, question: str, *, k: int = 12) -> list[Passage]:
    kws = keywords(question)
    passages: list[Passage] = []
    s = get_settings()

    def like_clauses(cols: list[Any]) -> Any:
        if not kws:
            return None
        return or_(*[c.ilike(f"%{kw}%") for c in cols for kw in kws])

    # Evidence
    ev_stmt = (
        select(Evidence, Source).outerjoin(Source, Source.id == Evidence.source_id).where(Evidence.case_id == case_id)
    )
    cl = like_clauses([Evidence.claim, Evidence.excerpt, Evidence.context])
    if cl is not None:
        ev_stmt = ev_stmt.where(cl)
    if not s.is_sqlite and kws:
        tsq = func.plainto_tsquery("english", " ".join(kws))
        ev_stmt = ev_stmt.order_by(
            func.ts_rank(func.to_tsvector("english", Evidence.claim + " " + Evidence.excerpt), tsq).desc()
        )
    else:
        ev_stmt = ev_stmt.order_by(Evidence.created_at.desc())
    for ev, src in (await session.execute(ev_stmt.limit(k * 2))).all():
        text = f"{ev.claim}" + (f" | excerpt: {ev.excerpt[:400]}" if ev.excerpt else "")
        passages.append(
            Passage(
                ev.display_id,
                "evidence",
                text,
                _score(text, kws) + (0.2 if ev.excerpt_verified else 0),
                {
                    "confidence": ev.confidence,
                    "type": ev.evidence_type,
                    "review": ev.review_state,
                    "source": src.url if src else None,
                    "source_tier": src.tier if src else None,
                    "collected_at": ev.collected_at.isoformat(),
                },
            )
        )
    # Findings
    f_stmt = select(Finding).where(Finding.case_id == case_id)
    cl = like_clauses([Finding.title, Finding.claim, Finding.assessment])
    if cl is not None:
        f_stmt = f_stmt.where(cl)
    for f in (await session.execute(f_stmt.limit(k))).scalars():
        text = f"{f.title}: {f.claim}" + (f" Assessment: {f.assessment[:300]}" if f.assessment else "")
        passages.append(
            Passage(
                f.display_id,
                "finding",
                text,
                _score(text, kws) + 0.1,
                {"confidence": f.confidence, "review": f.review_state},
            )
        )
    # Notes
    n_stmt = select(Note).where(Note.case_id == case_id)
    cl = like_clauses([Note.title, Note.body])
    if cl is not None:
        n_stmt = n_stmt.where(cl)
    for n in (await session.execute(n_stmt.limit(k // 2))).scalars():
        text = f"{n.title}: {n.body[:600]}" if n.title else n.body[:600]
        passages.append(Passage(f"note:{n.id}", "note", text, _score(text, kws), {"pinned": n.pinned}))
    # Snapshot excerpts (windows around keyword hits)
    if kws:
        snap_stmt = (
            select(SourceSnapshot, Source)
            .join(Source, Source.id == SourceSnapshot.source_id)
            .where(SourceSnapshot.case_id == case_id)
            .where(like_clauses([SourceSnapshot.text_content]))
            .order_by(SourceSnapshot.retrieved_at.desc())
            .limit(k)
        )
        for snap, src in (await session.execute(snap_stmt)).all():
            window = _window(snap.text_content, kws)
            if window:
                passages.append(
                    Passage(
                        src.display_id,
                        "snapshot",
                        window,
                        _score(window, kws) - 0.1,
                        {"url": src.url, "tier": src.tier, "retrieved_at": snap.retrieved_at.isoformat()},
                    )
                )
    # Entities (exact-ish)
    if kws:
        ent_stmt = (
            select(Entity)
            .where(Entity.case_id == case_id)
            .where(like_clauses([Entity.value, Entity.label]))
            .limit(k // 2)
        )
        for e in (await session.execute(ent_stmt)).scalars():
            passages.append(
                Passage(
                    e.display_id,
                    "entity",
                    f"{e.type} {e.value} (confidence {e.confidence}, {e.source_count} evidence)",
                    0.5,
                    {"type": e.type},
                )
            )
    passages.sort(key=lambda p: p.score, reverse=True)
    return passages[:k]


def _score(text: str, kws: list[str]) -> float:
    if not kws:
        return 0.0
    t = text.lower()
    return sum(1.0 for kw in kws if kw in t) / len(kws)


def _window(text: str, kws: list[str], width: int = 240) -> str:
    t = text.lower()
    for kw in kws:
        i = t.find(kw)
        if i >= 0:
            start = max(0, i - width // 2)
            return text[start : start + width].replace("\n", " ").strip()
    return ""


async def case_context(session: AsyncSession, case_id: uuid.UUID) -> dict[str, Any]:
    """Compact case summary for prompts: objective, targets, counts, top findings."""
    from eyohe.models.cases import Case, Target

    case = await session.get(Case, case_id)
    targets = list((await session.execute(select(Target).where(Target.case_id == case_id))).scalars())
    findings = list(
        (
            await session.execute(
                select(Finding).where(Finding.case_id == case_id).order_by(Finding.created_at.desc()).limit(10)
            )
        ).scalars()
    )
    counts = {}
    for name, model in (("evidence", Evidence), ("sources", Source), ("entities", Entity), ("findings", Finding)):
        counts[name] = int(
            (
                await session.execute(select(func.count()).select_from(model).where(model.case_id == case_id))
            ).scalar_one()
        )
    return {
        "case": case.display_id if case else None,
        "name": case.name if case else None,
        "objective": case.objective if case else "",
        "targets": [{"type": t.type, "value": t.normalized_value} for t in targets],
        "counts": counts,
        "findings": [{"id": f.display_id, "title": f.title, "confidence": f.confidence} for f in findings],
    }
