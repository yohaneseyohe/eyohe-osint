import asyncio
import io
import json
import shutil

import httpx
import pytest
import respx
from httpx import AsyncClient


async def _demo_case() -> str:
    from eyohe.core.db import get_session_factory
    from eyohe.services.demo import create_demo_case

    async with get_session_factory()() as db:
        case = await create_demo_case(db)
        await db.commit()
        return str(case.id)


async def test_reports_markdown_html_docx_and_pdf(auth_client: AsyncClient) -> None:
    cid = await _demo_case()
    ids = {}
    for fmt in ("markdown", "html", "docx", "pdf"):
        r = await auth_client.post("/api/v1/reports", json={"case_id": cid, "format": fmt})
        assert r.status_code == 202, r.text
        ids[fmt] = r.json()["id"]
    for fmt, rid in ids.items():
        for _ in range(600):
            r = await auth_client.get(f"/api/v1/reports/{rid}")
            if r.json()["status"] in ("READY", "FAILED"):
                break
            await asyncio.sleep(0.2)
        rep = r.json()
        if fmt == "pdf" and rep["status"] == "FAILED" and not shutil.which("chromium"):
            pytest.skip("no PDF engine available")
        assert rep["status"] == "READY", rep
        assert rep["sha256"] and rep["size_bytes"] > 500
        assert any(s["key"].startswith("key_findings") for s in rep["sections"])
        dl = await auth_client.get(f"/api/v1/reports/{rid}/download")
        assert dl.status_code == 200
        body = dl.content
        if fmt == "markdown":
            text = body.decode()
            assert "EYO-EV-" in text and "https://example-labs.test/about" in text and "DEMO DATA" in text
            assert "## Limitations" in text and "## Evidence Index" in text
        if fmt == "html":
            assert b"Evidence Index" in body and b"EYO-CASE-" in body
        if fmt == "pdf":
            assert body[:5] == b"%PDF-"
        if fmt == "docx":
            assert body[:2] == b"PK"
    # exports
    r = await auth_client.get(f"/api/v1/cases/{cid}/export", params={"format": "json"})
    pkg = r.json()
    assert pkg["eyohe_export"]["kind"] == "case_package" and len(pkg["evidence"]) == 3
    r = await auth_client.get(f"/api/v1/cases/{cid}/export", params={"format": "csv", "kind": "entities"})
    assert r.text.splitlines()[0].startswith("display_id,type,value")
    r = await auth_client.get(f"/api/v1/cases/{cid}/export", params={"format": "graphml"})
    assert "<graphml" in r.text and "POSSIBLY_SAME_ENTITY" not in r.text and "OWNS" in r.text


async def test_import_json_package_and_ioc_list(auth_client: AsyncClient) -> None:
    cid = await _demo_case()
    r = await auth_client.get(f"/api/v1/cases/{cid}/export", params={"format": "json"})
    pkg = r.content
    r = await auth_client.post("/api/v1/cases", json={"name": "Import target"})
    new_cid = r.json()["id"]
    files = {"file": ("package.json", io.BytesIO(pkg), "application/json")}
    r = await auth_client.post(f"/api/v1/cases/{new_cid}/import", files=files)
    assert r.status_code == 201, r.text
    assert r.json()["evidence"] == 3 and r.json()["sources"] == 3
    r = await auth_client.post(
        f"/api/v1/cases/{new_cid}/import",
        files={"file": ("iocs.txt", io.BytesIO(b"evil.example.org\n203.0.113.9\nnot an indicator!!\n"), "text/plain")},
    )
    assert r.json()["entities"] == 2 and r.json()["skipped"] == 1
    r = await auth_client.post(
        f"/api/v1/cases/{new_cid}/import", files={"file": ("bad.json", io.BytesIO(b'{"x":1}'), "application/json")}
    )
    assert r.status_code == 422


async def test_monitor_baseline_then_alert(auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from eyohe.collectors.base import CollectContext, CollectResult, EntityItem, EvidenceItem, SourceItem
    from eyohe.collectors.registry import collector_registry
    from eyohe.core.enums import EntityType, EvidenceType, SourceType, TargetType

    r = await auth_client.post("/api/v1/cases", json={"name": "Monitor case", "targets": ["example.com"]})
    cid = r.json()["id"]
    target_id = r.json()["targets"][0]["id"]
    state = {"a": ["93.184.216.34"]}

    class FakeDNS:
        name = "dns"

        async def collect(self, ctx: CollectContext, ttype: TargetType, value: str) -> CollectResult:
            res = CollectResult(collector="dns")
            res.sources.append(
                SourceItem(url=f"dns://{value}", source_type=SourceType.TECHNICAL_RECORD, title="dns", tier=3)
            )
            res.evidence.append(
                EvidenceItem(
                    claim=f"A {state['a']}",
                    evidence_type=EvidenceType.TECHNICAL_RECORD,
                    source_url=f"dns://{value}",
                    structured={"record_type": "A", "values": state["a"]},
                    entities=[EntityItem(EntityType.IP, ip) for ip in state["a"]],
                )
            )
            return res

    monkeypatch.setattr(collector_registry, "_collectors", {"dns": FakeDNS()})
    monkeypatch.setattr(collector_registry, "_loaded", True)
    r = await auth_client.post(
        "/api/v1/monitors",
        json={
            "case_id": cid,
            "name": "example.com DNS",
            "target_id": target_id,
            "checks": ["dns"],
            "schedule": "daily",
            "notify": {"telegram": True},
        },
    )
    assert r.status_code == 201, r.text
    mid = r.json()["id"]
    from eyohe.scheduler.monitors import run_monitor

    out = await run_monitor(mid)
    assert out["first_run"] is True and out["alerts"] == 0
    state["a"] = ["198.51.100.7"]
    out = await run_monitor(mid)
    assert out["alerts"] == 1
    r = await auth_client.get("/api/v1/alerts", params={"case_id": cid})
    alerts = r.json()["items"]
    assert alerts[0]["alert_type"] == "DOMAIN_CHANGE" and "198.51.100.7" in alerts[0]["message"]
    assert alerts[0]["delivered"]["telegram"].startswith("not configured")
    r = await auth_client.post(f"/api/v1/alerts/{alerts[0]['id']}/ack")
    assert r.json()["read"] is True
    r = await auth_client.get(f"/api/v1/monitors/{mid}")
    assert r.json()["run_count"] == 2 and r.json()["last_status"] == "OK"
    r = await auth_client.post(
        "/api/v1/monitors", json={"case_id": cid, "name": "bad", "target_value": "example.com", "checks": ["nmap"]}
    )
    assert r.status_code == 422


@respx.mock
async def test_monitor_handles_collector_failure(auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from eyohe.collectors.registry import collector_registry

    r = await auth_client.post("/api/v1/cases", json={"name": "Monitor fail", "targets": ["example.com"]})
    cid = r.json()["id"]

    class Boom:
        name = "ct_logs"

        async def collect(self, *a, **k):  # type: ignore[no-untyped-def]
            from eyohe.core.errors import CollectorError

            raise CollectorError("ct_logs", "crt.sh unavailable", retry_after_seconds=120)

    monkeypatch.setattr(collector_registry, "_collectors", {"ct_logs": Boom()})
    monkeypatch.setattr(collector_registry, "_loaded", True)
    r = await auth_client.post(
        "/api/v1/monitors", json={"case_id": cid, "name": "ct", "target_value": "example.com", "checks": ["ct"]}
    )
    from eyohe.scheduler.monitors import run_monitor

    out = await run_monitor(r.json()["id"])
    assert out["status"] == "ERROR" and "crt.sh unavailable" in out["errors"][0]
    r = await auth_client.get("/api/v1/alerts", params={"case_id": cid})
    assert r.json()["items"][0]["alert_type"] == "MONITOR_ERROR"
    _ = json, httpx  # keep imports used
