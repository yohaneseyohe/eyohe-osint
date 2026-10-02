"""Case-wide verification: recompute confidence for every finding/relationship from current evidence
and surface contradictions. Deterministic; the AI never sets confidence."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.enums import Confidence
from eyohe.models.entities import Relationship
from eyohe.models.findings import Finding
from eyohe.models.investigations import Investigation
from eyohe.services import entities as entity_service
from eyohe.services import findings as finding_service


async def verify_case(session: AsyncSession, case_id: uuid.UUID, inv: Investigation | None = None) -> dict[str, Any]:
    findings = list((await session.execute(select(Finding).where(Finding.case_id == case_id))).scalars())
    rels = list((await session.execute(select(Relationship).where(Relationship.case_id == case_id))).scalars())
    contradictions = 0
    by_label: dict[str, int] = {}
    for f in findings:
        await finding_service.refresh_finding(session, f)
        by_label[f.confidence] = by_label.get(f.confidence, 0) + 1
        if f.confidence == Confidence.CONTRADICTED:
            contradictions += 1
    for r in rels:
        r.confidence = await entity_service.compute_relationship_confidence(session, r)
    await session.flush()
    return {
        "findings": len(findings),
        "relationships": len(rels),
        "contradictions": contradictions,
        "by_confidence": by_label,
    }
