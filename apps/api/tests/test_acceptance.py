"""Offline end-to-end acceptance workflow (spec §96) using deterministic fake collectors so the test
needs no network. Every step mirrors what the UI does through the API."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient

from eyohe.collectors.base import (
    BaseCollector,
    CollectContext,
    CollectorHealth,
    CollectResult,
    EntityItem,
    EvidenceItem,
    RelationshipItem,
    SourceItem,
    TimelineItem,
)
from eyohe.core.enums import EntityType, EvidenceType, RelationshipType, SourceType, TargetType


class FakeDNS(BaseCollector):
    name = "dns"
    supported_targets = frozenset({TargetType.DOMAIN})

    async def health_check(self) -> CollectorHealth:
        return CollectorHealth(self.name, "ONLINE")

    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
        res = CollectResult(collector=self.name)
        res.sources.append(
            SourceItem(
                url=f"dns://{value}",
                source_type=SourceType.TECHNICAL_RECORD,
                title=f"DNS {value}",
                tier=3,
                text_content="A 93.184.216.34",
            )
        )
        dom, ip = EntityItem(EntityType.DOMAIN, value), EntityItem(EntityType.IP, "93.184.216.34")
        res.evidence.append(
            EvidenceItem(
                claim=f"DNS A record for {value}: 93.184.216.34",
                evidence_type=EvidenceType.TECHNICAL_RECORD,
                excerpt="A 93.184.216.34",
                source_url=f"dns://{value}",
                structured={"record_type": "A", "values": ["93.184.216.34"]},
                entities=[dom, ip],
                key="a",
            )
        )
        res.relationships.append(
            RelationshipItem(dom, ip, RelationshipType.RESOLVES_TO, rationale="DNS A record", evidence_keys=["a"])
        )
        return res


class FakeWeb(BaseCollector):
    name = "web_fetch"
    supported_targets = frozenset({TargetType.DOMAIN, TargetType.URL})

    async def health_check(self) -> CollectorHealth:
        return CollectorHealth(self.name, "ONLINE")

    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
        res = CollectResult(collector=self.name)
        url = f"https://{value}/"
        text = "Example Domain. This domain is for use in illustrative examples. Operated by Acme Example Labs. Code at https://github.com/acme-example-labs"
        res.sources.append(
            SourceItem(
                url=url,
                source_type=SourceType.WEBSITE,
                title="Example Domain",
                tier=1,
                text_content=text,
                content_type="text/html",
                http_status=200,
            )
        )
        dom = EntityItem(EntityType.DOMAIN, value)
        org = EntityItem(EntityType.ORGANIZATION, "Acme Example Labs")
        gh = EntityItem(EntityType.SOCIAL_ACCOUNT, "github:acme-example-labs", attributes={"platform": "github"})
        res.evidence.append(
            EvidenceItem(
                claim=f"Public page {url} states it is operated by Acme Example Labs",
                evidence_type=EvidenceType.DIRECT_STATEMENT,
                excerpt="Operated by Acme Example Labs",
                source_url=url,
                entities=[dom, org, gh],
                key="page",
            )
        )
        res.relationships.append(
            RelationshipItem(
                org, dom, RelationshipType.OWNS, rationale="stated on the public homepage", evidence_keys=["page"]
            )
        )
        res.relationships.append(
            RelationshipItem(dom, gh, RelationshipType.LINKS_TO, rationale="link on homepage", evidence_keys=["page"])
        )
        res.timeline.append(
            TimelineItem(
                occurred_at=datetime(2024, 5, 11, tzinfo=UTC),
                title="Homepage first observed mentioning Acme Example Labs",
                evidence_key="page",
                entities=[dom],
            )
        )
        return res


class FakeGitHub(BaseCollector):
    name = "github"
    supported_targets = frozenset({TargetType.DOMAIN})

    async def health_check(self) -> CollectorHealth:
        return CollectorHealth(self.name, "ONLINE")

    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
        res = CollectResult(collector=self.name)
        url = "https://github.com/acme-example-labs/site"
        res.sources.append(
            SourceItem(
                url=url,
                source_type=SourceType.CODE_REPOSITORY,
                title="acme-example-labs/site",
                tier=3,
                text_content="site for example.com",
            )
        )
        res.evidence.append(
            EvidenceItem(
                claim=f"Public repository acme-example-labs/site references {value}",
                evidence_type=EvidenceType.TECHNICAL_RECORD,
                excerpt="site for example.com",
                source_url=url,
                entities=[
                    EntityItem(EntityType.REPOSITORY, "acme-example-labs/site"),
                    EntityItem(
                        EntityType.SOCIAL_ACCOUNT, "github:acme-example-labs", attributes={"platform": "github"}
                    ),
                    EntityItem(EntityType.DOMAIN, value),
                ],
                key="repo",
            )
        )
        return res


class FailingRDAP(BaseCollector):
    name = "rdap"
    supported_targets = frozenset({TargetType.DOMAIN})

    async def health_check(self) -> CollectorHealth:
        return CollectorHealth(self.name, "ONLINE")

    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
        from eyohe.core.errors import CollectorError

        raise CollectorError(
            "rdap", "rdap.org rate limit reached", retry_after_seconds=42, impact="no registration data"
        )


@pytest.fixture
def fake_collectors(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    from eyohe.collectors.registry import collector_registry
    from eyohe.core.config import get_settings

    monkeypatch.setattr(
        collector_registry, "_collectors", {c.name: c for c in (FakeDNS(), FakeWeb(), FakeGitHub(), FailingRDAP())}
    )
    monkeypatch.setattr(collector_registry, "_loaded", True)
    monkeypatch.setattr(get_settings(), "search_providers", "")
    monkeypatch.setattr(get_settings(), "ollama_url", "http://127.0.0.1:9")
    yield


async def _wait(client: AsyncClient, inv_id: str, *statuses: str) -> dict:  # type: ignore[type-arg]
    for _ in range(600):
        r = await client.get(f"/api/v1/investigations/{inv_id}")
        if r.json()["status"] in statuses:
            return r.json()
        await asyncio.sleep(0.1)
    raise AssertionError(f"investigation never reached {statuses}: {r.json()['status']}")


async def test_full_acceptance_workflow(auth_client: AsyncClient, fake_collectors: None) -> None:
    # 3-5. create case with target + objective
    r = await auth_client.post(
        "/api/v1/cases",
        json={
            "name": "Acceptance: example.com",
            "objective": "Identify public infrastructure and organisations behind example.com",
            "targets": ["example.com"],
        },
    )
    case = r.json()
    cid = case["id"]
    # 6. plan (template; AI offline in this test)
    r = await auth_client.post(
        "/api/v1/investigations/start",
        json={"case_id": cid, "request_text": "Investigate example.com", "use_ai": False},
    )
    inv = r.json()
    assert inv["status"] == "AWAITING_APPROVAL" and all(t["rationale"] for t in inv["tasks"])
    # 7. approve → 8-12. collectors run, events, sources, evidence, entities, relationships, timeline
    r = await auth_client.post(f"/api/v1/investigations/{inv['id']}/approve")
    assert r.json()["status"] == "RUNNING"
    detail = await _wait(auth_client, inv["id"], "COMPLETED", "FAILED", "STOPPED")
    assert detail["status"] == "COMPLETED"
    statuses = {t["task_type"]: t for t in detail["tasks"]}
    assert statuses["dns"]["status"] == "COMPLETED" and statuses["web_fetch"]["status"] == "COMPLETED"
    assert statuses["rdap"]["status"] == "FAILED" and "rate limit" in statuses["rdap"]["error"]
    assert statuses["correlate"]["status"] == "COMPLETED" and statuses["verify"]["status"] == "COMPLETED"
    assert statuses["summarize"]["status"] == "SKIPPED"  # Ollama offline → honest skip, nothing fabricated
    r = await auth_client.get(f"/api/v1/investigations/{inv['id']}/events")
    events = r.json()
    types = [e["event_type"] for e in events]
    assert (
        "SOURCE_DISCOVERED" in types
        and "EVIDENCE_CREATED" in types
        and "RELATIONSHIP_CREATED" in types
        and "TASK_FAILED" in types
    )
    failed = next(e for e in events if e["event_type"] == "TASK_FAILED")
    assert failed["data"]["retry_after_seconds"] == 42 and failed["data"]["collector"] == "rdap"
    r = await auth_client.get(f"/api/v1/cases/{cid}/sources")
    assert r.json()["total"] == 3
    r = await auth_client.get(f"/api/v1/cases/{cid}/evidence")
    assert r.json()["total"] == 3 and all(e["source_id"] for e in r.json()["items"])
    r = await auth_client.get(f"/api/v1/cases/{cid}/entities")
    ent_types = {e["type"] for e in r.json()["items"]}
    assert {"DOMAIN", "IP", "ORGANIZATION", "SOCIAL_ACCOUNT", "REPOSITORY"} <= ent_types
    r = await auth_client.get(f"/api/v1/cases/{cid}/graph")
    g = r.json()
    assert g["stats"]["edges"] >= 3 and all(e["evidence_count"] >= 1 for e in g["edges"])
    r = await auth_client.get(f"/api/v1/cases/{cid}/timeline")
    assert len(r.json()) == 1
    # 13. correlation proposed a relationship linking the GitHub account to the organisation? (name similarity)
    r = await auth_client.get(f"/api/v1/cases/{cid}/relationships")
    rels = r.json()
    assert any(x["type"] == "OWNS" for x in rels)
    # 15-16. analyst creates a finding from two independent sources → CORROBORATED; Why? explains it
    r = await auth_client.get(f"/api/v1/cases/{cid}/evidence")
    ev = {e["collector"]: e for e in r.json()["items"]}
    r = await auth_client.post(
        f"/api/v1/cases/{cid}/findings",
        json={
            "title": "example.com is operated by Acme Example Labs",
            "claim": "The homepage and a public repository both tie example.com to Acme Example Labs",
            "supporting": [ev["web_fetch"]["id"], ev["github"]["id"]],
            "category": "organisation",
        },
    )
    finding = r.json()
    assert finding["confidence"] == "CORROBORATED"
    # 17. Why?
    r = await auth_client.get(f"/api/v1/findings/{finding['id']}/why")
    why = r.json()
    assert len(why["chain"]) == 2 and all(c["source"]["url"] for c in why["chain"])
    assert "2 independent sources" in why["reasoning"]
    # 18. edge Why?
    owns = next(x for x in rels if x["type"] == "OWNS")
    r = await auth_client.get(f"/api/v1/relationships/{owns['id']}")
    assert r.json()["why"]["chain"][0]["evidence_id"].startswith("EYO-EV-")
    # 19-20. report with sources and evidence IDs
    r = await auth_client.post("/api/v1/reports", json={"case_id": cid, "format": "markdown"})
    rid = r.json()["id"]
    for _ in range(300):
        r = await auth_client.get(f"/api/v1/reports/{rid}")
        if r.json()["status"] in ("READY", "FAILED"):
            break
        await asyncio.sleep(0.1)
    assert r.json()["status"] == "READY", r.json()
    text = (await auth_client.get(f"/api/v1/reports/{rid}/download")).text
    assert (
        ev["web_fetch"]["display_id"] in text
        and "https://example.com/" in text
        and "https://github.com/acme-example-labs/site" in text
    )
    assert "rate limit" in text  # limitations section records the failed collector honestly
    # 21-22. reopen case, resume investigation (retries the failed task)
    r = await auth_client.patch(f"/api/v1/cases/{cid}", json={"status": "COMPLETED"})
    r = await auth_client.patch(f"/api/v1/cases/{cid}", json={"status": "ACTIVE"})
    assert r.json()["status"] == "ACTIVE"
    r = await auth_client.post(f"/api/v1/investigations/{inv['id']}/control", json={"action": "resume"})
    detail = await _wait(auth_client, inv["id"], "COMPLETED", "FAILED", "STOPPED")
    assert detail["status"] == "COMPLETED"
    assert next(t for t in detail["tasks"] if t["task_type"] == "rdap")["attempts"] == 2
    # 23. audit log
    r = await auth_client.get("/api/v1/audit", params={"case_id": cid, "page_size": 500})
    actions = {a["action"] for a in r.json()["items"]}
    assert {
        "CASE_CREATED",
        "INVESTIGATION_APPROVED",
        "EVIDENCE_CREATED",
        "RELATIONSHIP_CREATED",
        "FINDING_CREATED",
        "REPORT_GENERATED",
        "INVESTIGATION_RESUMED",
    } <= actions
    # 24-25. no fabricated sources (every evidence has a source URL), no secrets
    r = await auth_client.get(f"/api/v1/cases/{cid}/sources")
    assert all(s["url"] for s in r.json()["items"])
    assert "ghp_" not in text and "AKIA" not in text


async def test_pause_and_stop_persist_state(
    auth_client: AsyncClient, fake_collectors: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    import eyohe.collectors.registry as reg

    class SlowDNS(FakeDNS):
        async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
            await asyncio.sleep(0.6)
            return await super().collect(ctx, target_type, value)

    reg.collector_registry._collectors["dns"] = SlowDNS()
    r = await auth_client.post("/api/v1/cases", json={"name": "Pause", "targets": ["example.org"]})
    cid = r.json()["id"]
    r = await auth_client.post(
        "/api/v1/investigations/start", json={"case_id": cid, "request_text": "x", "use_ai": False}
    )
    inv = r.json()
    await auth_client.post(f"/api/v1/investigations/{inv['id']}/approve")
    await asyncio.sleep(0.1)
    r = await auth_client.post(f"/api/v1/investigations/{inv['id']}/control", json={"action": "pause"})
    assert r.status_code == 200
    detail = await _wait(auth_client, inv["id"], "PAUSED", "COMPLETED")
    assert detail["status"] == "PAUSED"
    pending = [t for t in detail["tasks"] if t["status"] == "PENDING"]
    assert pending, "pause should leave later tasks pending"
    r = await auth_client.post(f"/api/v1/investigations/{inv['id']}/control", json={"action": "stop"})
    assert r.json()["status"] == "STOPPED"
    r = await auth_client.post(f"/api/v1/investigations/{inv['id']}/control", json={"action": "resume"})
    detail = await _wait(auth_client, inv["id"], "COMPLETED", "FAILED", "STOPPED")
    assert detail["status"] == "COMPLETED"
