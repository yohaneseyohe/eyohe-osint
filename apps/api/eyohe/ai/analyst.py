"""AI analyst Q&A over a case. Retrieval-first: only retrieved passages (with IDs) reach the model,
and the answer must cite them. Sentences that cite nothing are flagged; unknown IDs are stripped."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.ai.ollama import OllamaClient, OllamaUnavailableError
from eyohe.ai.retrieval import Passage, case_context, retrieve

SYSTEM = """You are the AI analyst inside Eyohe OSINT. Answer the analyst's question using ONLY the provided case passages.
Rules:
- Cite passages by their reference in square brackets, e.g. [EYO-EV-000012]. Every factual sentence needs at least one citation.
- If the passages do not contain the answer, reply exactly: "Not found in the collected evidence." and suggest which collector or search could find it.
- Distinguish facts (technical records, official sources) from statements by third parties ("according to a Reddit post…") and from inference ("this may indicate…").
- Never invent IDs, URLs, dates, usernames or sources. Keep answers concise and structured."""

_CITE = re.compile(r"\[(EYO-[A-Z]+-\d{6}|note:[0-9a-f-]{36})\]")


async def answer_question(session: AsyncSession, case_id: uuid.UUID, question: str, *, k: int = 12) -> dict[str, Any]:
    passages = await retrieve(session, case_id, question, k=k)
    ctx = await case_context(session, case_id)
    if not passages:
        return {
            "answer": "Not found in the collected evidence. No passages in this case match the question; consider running a search or collector for it.",
            "citations": [],
            "passages": [],
            "uncited_sentences": [],
            "model": None,
        }
    client = OllamaClient()
    if not await client.available():
        raise OllamaUnavailableError(
            "Ollama is not reachable; the AI analyst is offline. Retrieved passages are still shown."
        )
    payload = {
        "case": {k: v for k, v in ctx.items() if k in ("case", "name", "objective", "targets")},
        "passages": [{"ref": p.ref, "kind": p.kind, "text": p.text[:700], "meta": p.meta} for p in passages],
    }
    resp = await client.chat(
        [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Question: {question}\n\nPassages:\n{json.dumps(payload, default=str)}"},
        ],
        purpose="analyst",
        temperature=0.1,
        max_tokens=900,
    )
    answer = (resp.get("message", {}).get("content") or "").strip()
    answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.S).strip()
    known = {p.ref for p in passages}
    cited = []
    for ref in _CITE.findall(answer):
        if ref in known and ref not in cited:
            cited.append(ref)
    # Strip citations of IDs that were not provided (hallucinated references).
    answer = _CITE.sub(lambda m: m.group(0) if m.group(1) in known else "[unverified reference removed]", answer)
    uncited = [
        s_.strip()
        for s_ in re.split(r"(?<=[.!?])\s+", answer)
        if len(s_.strip()) > 40 and not _CITE.search(s_) and "not found" not in s_.lower()
    ]
    return {
        "answer": answer,
        "citations": [_passage_dict(p) for p in passages if p.ref in cited],
        "passages": [_passage_dict(p) for p in passages],
        "uncited_sentences": uncited[:10],
        "model": client.model,
    }


def _passage_dict(p: Passage) -> dict[str, Any]:
    return {"ref": p.ref, "kind": p.kind, "text": p.text, "score": round(p.score, 3), "meta": p.meta}
