"""Entity resolution: propose POSSIBLY_SAME_ENTITY / ASSOCIATED_WITH links across collectors.

Rules are conservative and every proposal cites the evidence that mentions both entities.
Proposals are never auto-confirmed; the analyst reviews them (human-in-the-loop)."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.enums import EntityType, RelationshipType
from eyohe.core.urlnorm import registrable_domain
from eyohe.models.entities import Entity, Relationship
from eyohe.services import entities as entity_service


async def correlate_case(session: AsyncSession, case_id: uuid.UUID) -> dict[str, Any]:
    ents = list(
        (
            await session.execute(select(Entity).where(Entity.case_id == case_id, Entity.merged_into_id.is_(None)))
        ).scalars()
    )
    existing = {
        (r.source_entity_id, r.target_entity_id, r.type)
        for r in (await session.execute(select(Relationship).where(Relationship.case_id == case_id))).scalars()
    }
    by_type: dict[str, list[Entity]] = defaultdict(list)
    for e in ents:
        by_type[e.type].append(e)
    created = 0
    proposals: list[dict[str, str]] = []

    async def link(a: Entity, b: Entity, rtype: RelationshipType, rationale: str) -> None:
        nonlocal created
        if a.id == b.id or (a.id, b.id, str(rtype)) in existing or (b.id, a.id, str(rtype)) in existing:
            return
        shared = [uuid.UUID(x) for x in set(a.evidence_ids or []) & set(b.evidence_ids or [])]
        ev_ids = shared or [uuid.UUID(x) for x in (a.evidence_ids or [])[:2] + (b.evidence_ids or [])[:2]]
        if not ev_ids:
            return
        await entity_service.create_relationship(
            session,
            case_id,
            a,
            b,
            rtype,
            evidence_ids=ev_ids,
            rationale=rationale,
            attributes={"proposed_by": "resolver", "shared_evidence": len(shared)},
        )
        existing.add((a.id, b.id, str(rtype)))
        created += 1
        proposals.append({"source": a.display_id, "target": b.display_id, "type": str(rtype), "rationale": rationale})

    # 1. Same handle across platforms → POSSIBLY_SAME_ENTITY (capped at POSSIBLE until reviewed).
    handles: dict[str, list[Entity]] = defaultdict(list)
    for e in by_type.get(EntityType.SOCIAL_ACCOUNT, []):
        handle = e.normalized_value.split(":", 1)[-1]
        if len(handle) >= 4:
            handles[handle].append(e)
    for e in by_type.get(EntityType.USERNAME, []):
        handles[e.normalized_value].append(e)
    for handle, group in handles.items():
        if len(group) < 2:
            continue
        for a in group:
            for b in group:
                if a.id < b.id:
                    await link(
                        a,
                        b,
                        RelationshipType.POSSIBLY_SAME_ENTITY,
                        f"Identical handle '{handle}' on different platforms. "
                        "Handles are not unique identifiers; requires analyst confirmation.",
                    )

    # 2. Email local-part equals a known username → POSSIBLY_SAME_ENTITY; email domain ↔ domain → ASSOCIATED_WITH.
    domains = {d.normalized_value: d for d in by_type.get(EntityType.DOMAIN, [])}
    usernames = {u.normalized_value: u for u in by_type.get(EntityType.USERNAME, [])}
    for em in by_type.get(EntityType.EMAIL, []):
        local, _, dom = em.normalized_value.partition("@")
        if local in usernames and len(local) >= 4:
            await link(
                em,
                usernames[local],
                RelationshipType.POSSIBLY_SAME_ENTITY,
                f"Email local part '{local}' matches a username seen in public sources.",
            )
        reg = registrable_domain(dom)
        if reg in domains:
            await link(
                em, domains[reg], RelationshipType.ASSOCIATED_WITH, "Email address uses a domain under investigation."
            )

    # 3. URLs/repositories hosted on a known domain → HOSTED_ON / REFERENCES.
    for u in by_type.get(EntityType.URL, []):
        reg = registrable_domain(u.normalized_value)
        if reg in domains:
            await link(u, domains[reg], RelationshipType.HOSTED_ON, "URL is served from a domain under investigation.")

    # 4. Organisation name appears in a social account label (e.g. GitHub org) → ASSOCIATED_WITH.
    for org in by_type.get(EntityType.ORGANIZATION, []) + by_type.get(EntityType.COMPANY, []):
        token = org.normalized_value.replace(" ", "")
        if len(token) < 5:
            continue
        for acct in by_type.get(EntityType.SOCIAL_ACCOUNT, []):
            handle = acct.normalized_value.split(":", 1)[-1].replace("-", "").replace("_", "")
            if token in handle or (handle in token and len(handle) >= 5):
                await link(
                    acct,
                    org,
                    RelationshipType.ASSOCIATED_WITH,
                    f"Account handle resembles organisation name '{org.value}' (name similarity only).",
                )
    await session.flush()
    return {"entities": len(ents), "relationships": created, "proposals": proposals[:50]}
