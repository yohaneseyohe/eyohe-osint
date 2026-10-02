"""Optional synthetic demo dataset. Everything is fictional and flagged ``is_demo`` so the UI can
label it DEMO DATA. No real people, domains (.test TLD) or organisations are used."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.enums import EntityType, EvidenceType, RelationshipType, SourceType
from eyohe.models.cases import Case
from eyohe.services import cases as case_service
from eyohe.services import entities as entity_service
from eyohe.services import evidence as evidence_service
from eyohe.services import findings as finding_service


async def create_demo_case(session: AsyncSession, actor=None) -> Case:  # type: ignore[no-untyped-def]
    case = await case_service.create_case(
        session,
        name="DEMO: Acme Example Labs",
        actor=actor,
        is_demo=True,
        description=(
            "DEMO DATA — a fictional investigation used to demonstrate the workstation. Every entity here is invented."
        ),
        objective="Demonstrate evidence-backed findings, graph, timeline and reporting with fictional data.",
        tags=["demo", "fictional"],
        targets=["example-labs.test", "demo_user_42"],
    )
    cid = case.id
    site = await evidence_service.upsert_source(
        session,
        cid,
        url="https://example-labs.test/about",
        source_type=SourceType.WEBSITE,
        collector="demo",
        tier=1,
        title="About — Acme Example Labs (fictional)",
        publisher="Acme Example Labs",
        is_demo=True,
    )
    snap = await evidence_service.add_snapshot(
        session,
        site,
        text_content=(
            "Acme Example Labs is a fictional research studio. Our code lives at github.com/acme-example-labs. "
            "Contact: hello@example-labs.test"
        ),
        title=site.title,
        http_status=200,
        content_type="text/html",
    )
    repo = await evidence_service.upsert_source(
        session,
        cid,
        url="https://github.com/acme-example-labs/demo-site",
        source_type=SourceType.CODE_REPOSITORY,
        collector="demo",
        tier=3,
        title="acme-example-labs/demo-site (fictional)",
        publisher="GitHub",
        is_demo=True,
    )
    reddit = await evidence_service.upsert_source(
        session,
        cid,
        url="https://www.reddit.com/r/example/comments/demo123/acme_example_labs_launch/",
        source_type=SourceType.FORUM,
        collector="demo",
        tier=4,
        title="Acme Example Labs launch thread (fictional)",
        publisher="Reddit",
        author="u/demo_user_42",
        published_at=datetime(2025, 4, 22, tzinfo=UTC),
        is_demo=True,
    )
    e1 = await evidence_service.create_evidence(
        session,
        cid,
        claim="The fictional website states its code is hosted under github.com/acme-example-labs",
        evidence_type=EvidenceType.DIRECT_STATEMENT,
        collector="demo",
        source=site,
        snapshot=snap,
        excerpt="Our code lives at github.com/acme-example-labs",
        is_demo=True,
    )
    e2 = await evidence_service.create_evidence(
        session,
        cid,
        claim="A public repository 'demo-site' exists under the acme-example-labs organisation (fictional)",
        evidence_type=EvidenceType.TECHNICAL_RECORD,
        collector="demo",
        source=repo,
        structured={"stars": 3},
        is_demo=True,
    )
    e3 = await evidence_service.create_evidence(
        session,
        cid,
        claim="A Reddit user identified as u/demo_user_42 stated that they maintain the Acme Example Labs website",
        evidence_type=EvidenceType.PUBLIC_STATEMENT,
        collector="demo",
        source=reddit,
        excerpt="I maintain the Acme Example Labs website in my spare time",
        observed_at=datetime(2025, 4, 22, tzinfo=UTC),
        is_demo=True,
    )
    org = await entity_service.upsert_entity(
        session, cid, EntityType.ORGANIZATION, "Acme Example Labs", evidence_id=e1.id, is_demo=True
    )
    dom = await entity_service.upsert_entity(
        session, cid, EntityType.DOMAIN, "example-labs.test", evidence_id=e1.id, is_demo=True
    )
    gh = await entity_service.upsert_entity(
        session,
        cid,
        EntityType.SOCIAL_ACCOUNT,
        "github:acme-example-labs",
        label="acme-example-labs (GitHub)",
        evidence_id=e2.id,
        is_demo=True,
    )
    user = await entity_service.upsert_entity(
        session, cid, EntityType.USERNAME, "demo_user_42", evidence_id=e3.id, is_demo=True
    )
    for ev, ids in ((e1, [org.id, dom.id, gh.id]), (e2, [gh.id]), (e3, [user.id, org.id])):
        await evidence_service.link_entities(session, ev, ids)
    await entity_service.create_relationship(
        session,
        cid,
        org,
        dom,
        RelationshipType.OWNS,
        evidence_ids=[e1.id],
        rationale="Official (fictional) site presents the domain as its own.",
        is_demo=True,
    )
    await entity_service.create_relationship(
        session,
        cid,
        org,
        gh,
        RelationshipType.LINKS_TO,
        evidence_ids=[e1.id, e2.id],
        rationale="Website links to the GitHub organisation; repository exists.",
        is_demo=True,
    )
    await entity_service.create_relationship(
        session,
        cid,
        user,
        org,
        RelationshipType.ASSOCIATED_WITH,
        evidence_ids=[e3.id],
        rationale="Self-reported association in a public forum post (uncorroborated).",
        is_demo=True,
    )
    await finding_service.create_finding(
        session,
        cid,
        title="Website and GitHub organisation belong to the same (fictional) organisation",
        claim="Acme Example Labs publishes its code under the GitHub organisation acme-example-labs.",
        supporting=[e1.id, e2.id],
        assessment="Two independent public sources agree.",
        category="infrastructure",
        proposed_by="demo",
        is_demo=True,
    )
    await finding_service.create_finding(
        session,
        cid,
        title="u/demo_user_42 may be associated with Acme Example Labs",
        claim="A Reddit account claims to maintain the organisation's website.",
        supporting=[e3.id],
        assessment="Single self-reported community statement; requires corroboration before any attribution.",
        category="identity",
        proposed_by="demo",
        is_demo=True,
    )
    await finding_service.add_timeline_event(
        session,
        cid,
        occurred_at=datetime(2025, 4, 22, tzinfo=UTC),
        title="Reddit launch thread published (fictional)",
        evidence_id=e3.id,
        entity_ids=[str(user.id)],
        confidence=e3.confidence,
        is_demo=True,
    )
    await finding_service.add_timeline_event(
        session,
        cid,
        occurred_at=datetime(2024, 11, 3, tzinfo=UTC),
        title="Demo repository first observed (fictional)",
        evidence_id=e2.id,
        entity_ids=[str(gh.id)],
        confidence=e2.confidence,
        is_demo=True,
    )
    await case_service.refresh_counts(session, cid)
    return case
