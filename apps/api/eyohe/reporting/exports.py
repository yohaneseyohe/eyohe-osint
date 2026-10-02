"""Case exports: JSON package, CSV (entities/evidence/sources), GraphML."""

from __future__ import annotations

import csv
import io
import json
import uuid
from typing import Any
from xml.sax.saxutils import escape

from sqlalchemy.ext.asyncio import AsyncSession

from eyohe import __version__
from eyohe.core.db import utcnow
from eyohe.reporting.builder import build_report_data


async def export_json(session: AsyncSession, case_id: uuid.UUID) -> dict[str, Any]:
    d = await build_report_data(session, case_id, analyst=None)
    return {
        "eyohe_export": {"version": __version__, "exported_at": utcnow().isoformat(), "kind": "case_package"},
        "case": {
            "display_id": d.case.display_id,
            "name": d.case.name,
            "description": d.case.description,
            "objective": d.case.objective,
            "status": d.case.status,
            "priority": d.case.priority,
            "tags": d.case.tags,
            "classification": d.case.classification,
            "is_demo": d.case.is_demo,
        },
        "targets": [
            {"type": t.type, "value": t.value, "label": t.label, "is_primary": t.is_primary} for t in d.targets
        ],
        "sources": [
            {
                "display_id": s.display_id,
                "url": s.url,
                "canonical_url": s.canonical_url,
                "source_type": s.source_type,
                "title": s.title,
                "publisher": s.publisher,
                "author": s.author,
                "published_at": s.published_at,
                "collected_at": s.collected_at,
                "collector": s.collector,
                "tier": s.tier,
                "reliability_note": s.reliability_note,
                "metadata": s.metadata_,
            }
            for s in d.sources
        ],
        "evidence": d.evidence,
        "entities": [
            {
                "display_id": e.display_id,
                "type": e.type,
                "value": e.value,
                "label": e.label,
                "confidence": e.confidence,
                "first_seen": e.first_seen,
                "last_seen": e.last_seen,
                "attributes": e.attributes,
                "is_target": e.is_target,
                "evidence_ids": e.evidence_ids,
            }
            for e in d.entities
        ],
        "relationships": d.relationships,
        "findings": d.findings,
        "timeline": [
            {
                "occurred_at": t.occurred_at,
                "precision": t.precision,
                "title": t.title,
                "description": t.description,
                "event_kind": t.event_kind,
                "confidence": t.confidence,
            }
            for t in d.timeline
        ],
        "notes": [{"title": n.title, "body": n.body, "pinned": n.pinned, "created_at": n.created_at} for n in d.notes],
        "stats": d.stats,
        "limitations": d.limitations,
    }


async def export_csv(session: AsyncSession, case_id: uuid.UUID, kind: str) -> str:
    d = await build_report_data(session, case_id, analyst=None)
    buf = io.StringIO()
    w = csv.writer(buf)
    if kind == "entities":
        w.writerow(
            [
                "display_id",
                "type",
                "value",
                "label",
                "confidence",
                "evidence_count",
                "first_seen",
                "last_seen",
                "is_target",
            ]
        )
        for e in d.entities:
            w.writerow(
                [
                    e.display_id,
                    e.type,
                    e.value,
                    e.label,
                    e.confidence,
                    e.source_count,
                    e.first_seen.isoformat(),
                    e.last_seen.isoformat(),
                    e.is_target,
                ]
            )
    elif kind == "evidence":
        w.writerow(
            [
                "display_id",
                "type",
                "claim",
                "excerpt",
                "excerpt_verified",
                "confidence",
                "review_state",
                "collector",
                "collected_at",
                "source_id",
                "source_url",
            ]
        )
        for ev in d.evidence:
            w.writerow(
                [
                    ev["id"],
                    ev["type"],
                    ev["claim"],
                    ev["excerpt"],
                    ev["excerpt_verified"],
                    ev["confidence"],
                    ev["review_state"],
                    ev["collector"],
                    ev["collected_at"].isoformat(),
                    ev["source"]["id"] if ev["source"] else "",
                    ev["source"]["url"] if ev["source"] else "",
                ]
            )
    elif kind == "sources":
        w.writerow(
            ["display_id", "url", "title", "type", "tier", "publisher", "published_at", "collected_at", "collector"]
        )
        for s in d.sources:
            w.writerow(
                [
                    s.display_id,
                    s.url,
                    s.title,
                    s.source_type,
                    s.tier,
                    s.publisher,
                    s.published_at.isoformat() if s.published_at else "",
                    s.collected_at.isoformat(),
                    s.collector,
                ]
            )
    elif kind == "relationships":
        w.writerow(
            [
                "display_id",
                "source",
                "source_type",
                "type",
                "target",
                "target_type",
                "confidence",
                "review_state",
                "evidence_ids",
                "rationale",
            ]
        )
        for r in d.relationships:
            w.writerow(
                [
                    r["id"],
                    r["source"],
                    r["source_type"],
                    r["type"],
                    r["target"],
                    r["target_type"],
                    r["confidence"],
                    r["review_state"],
                    " ".join(r["evidence_ids"]),
                    r["rationale"],
                ]
            )
    elif kind == "findings":
        w.writerow(
            ["display_id", "title", "claim", "category", "confidence", "review_state", "supporting", "contradicting"]
        )
        for f in d.findings:
            w.writerow(
                [
                    f["id"],
                    f["title"],
                    f["claim"],
                    f["category"],
                    f["confidence"],
                    f["review_state"],
                    " ".join(e["id"] for e in f["supporting"]),
                    " ".join(e["id"] for e in f["contradicting"]),
                ]
            )
    else:
        raise ValueError("unknown csv kind")
    return buf.getvalue()


async def export_graphml(session: AsyncSession, case_id: uuid.UUID) -> str:
    d = await build_report_data(session, case_id, analyst=None)
    by_value = {(e.type, e.value): e for e in d.entities}
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '<key id="type" for="node" attr.name="type" attr.type="string"/>',
        '<key id="label" for="node" attr.name="label" attr.type="string"/>',
        '<key id="confidence" for="all" attr.name="confidence" attr.type="string"/>',
        '<key id="rel" for="edge" attr.name="relationship" attr.type="string"/>',
        '<key id="evidence" for="edge" attr.name="evidence_ids" attr.type="string"/>',
        '<key id="target" for="node" attr.name="is_target" attr.type="boolean"/>',
        f'<graph id="{escape(d.case.display_id)}" edgedefault="directed">',
    ]
    for e in d.entities:
        out.append(
            f'<node id="{escape(e.display_id)}"><data key="type">{escape(e.type)}</data><data key="label">{escape(e.value)}</data><data key="confidence">{escape(e.confidence)}</data><data key="target">{"true" if e.is_target else "false"}</data></node>'
        )
    for i, r in enumerate(d.relationships):
        s = by_value.get((r["source_type"], r["source"]))
        t = by_value.get((r["target_type"], r["target"]))
        if s and t:
            out.append(
                f'<edge id="e{i}" source="{escape(s.display_id)}" target="{escape(t.display_id)}"><data key="rel">{escape(r["type"])}</data><data key="confidence">{escape(r["confidence"])}</data><data key="evidence">{escape(" ".join(r["evidence_ids"]))}</data></edge>'
            )
    out.append("</graph></graphml>")
    return "\n".join(out)


def dumps(obj: Any) -> str:
    return json.dumps(obj, default=str, indent=2)
