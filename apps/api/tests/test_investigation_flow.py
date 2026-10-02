import asyncio

from httpx import AsyncClient


async def test_plan_approve_run_resume(auth_client: AsyncClient, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    # Keep this flow test offline: no collector plugins, so tasks are SKIPPED (never faked).
    from eyohe.collectors.registry import collector_registry

    monkeypatch.setattr(collector_registry, "_collectors", {})
    monkeypatch.setattr(collector_registry, "_loaded", True)
    from eyohe.core.config import get_settings

    monkeypatch.setattr(get_settings(), "search_providers", "")  # search → NOT_CONFIGURED → task skipped
    monkeypatch.setattr(get_settings(), "ollama_url", "http://127.0.0.1:9")  # AI offline → summarize skipped
    r = await auth_client.post("/api/v1/cases", json={"name": "Flow", "targets": ["example.com"]})
    cid = r.json()["id"]
    r = await auth_client.post(
        "/api/v1/investigations/start",
        json={"case_id": cid, "request_text": "Investigate example.com public infrastructure", "use_ai": False},
    )
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["status"] == "AWAITING_APPROVAL" and inv["plan_source"] == "template"
    types = [t["task_type"] for t in inv["tasks"]]
    assert types[:3] == ["dns", "rdap", "ct_logs"] and "verify" in types
    assert all(t["rationale"] for t in inv["tasks"])
    assert inv["plan"]["branches"]

    # Analyst disables a branch/task before approval
    reddit = next(t for t in inv["tasks"] if t["task_type"] == "reddit")
    r = await auth_client.patch(
        f"/api/v1/investigations/{inv['id']}/plan", json={"tasks": [{"id": reddit["id"], "enabled": False}]}
    )
    assert next(t for t in r.json()["tasks"] if t["id"] == reddit["id"])["status"] == "DISABLED"

    # Invalid transition is explained
    r = await auth_client.post(f"/api/v1/investigations/{inv['id']}/control", json={"action": "pause"})
    assert r.status_code == 409 and r.json()["code"] == "invalid_transition"

    r = await auth_client.post(f"/api/v1/investigations/{inv['id']}/approve")
    assert r.status_code == 200 and r.json()["status"] == "RUNNING"

    # Embedded runner executes; with no collectors registered tasks are SKIPPED or fail honestly, not faked.
    for _ in range(600):
        await asyncio.sleep(0.1)
        r = await auth_client.get(f"/api/v1/investigations/{inv['id']}")
        if r.json()["status"] in ("COMPLETED", "FAILED", "STOPPED"):
            break
    detail = r.json()
    assert detail["status"] == "COMPLETED", detail
    statuses = {t["task_type"]: t["status"] for t in detail["tasks"]}
    assert statuses["reddit"] == "DISABLED"
    assert all(s in ("SKIPPED", "COMPLETED", "DISABLED", "FAILED") for s in statuses.values())
    assert statuses["verify"] == "COMPLETED" and statuses["dns"] == "SKIPPED"

    # Events are real, ordered, and replayable
    r = await auth_client.get(f"/api/v1/investigations/{inv['id']}/events")
    events = r.json()
    seqs = [e["seq"] for e in events]
    assert seqs == sorted(seqs) and seqs[0] == 1
    kinds = {e["event_type"] for e in events}
    assert {"PLAN", "PLAN_APPROVED", "TASK_STARTED", "VERIFICATION_STARTED", "STATUS_CHANGED"} <= kinds
    assert not any("fake" in e["message"].lower() for e in events)

    # Status summary derives from task state
    r = await auth_client.get(f"/api/v1/investigations/{inv['id']}/status")
    s = r.json()
    assert s["progress"] == 100 and s["status"] == "COMPLETED"

    # Re-run (expand research) is allowed from COMPLETED
    r = await auth_client.post(f"/api/v1/investigations/{inv['id']}/control", json={"action": "resume"})
    assert r.status_code == 200

    # Audit trail
    r = await auth_client.get("/api/v1/audit", params={"case_id": cid})
    actions = {a["action"] for a in r.json()["items"]}
    assert {"INVESTIGATION_CREATED", "INVESTIGATION_APPROVED", "INVESTIGATION_RESUMED"} <= actions


async def test_investigation_requires_target(auth_client: AsyncClient) -> None:
    r = await auth_client.post("/api/v1/cases", json={"name": "No targets"})
    cid = r.json()["id"]
    r = await auth_client.post(
        "/api/v1/investigations/start", json={"case_id": cid, "request_text": "x", "use_ai": False}
    )
    assert r.status_code == 422 and "target" in r.json()["message"].lower()
