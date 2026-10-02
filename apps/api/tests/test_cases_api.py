from httpx import AsyncClient


async def test_case_lifecycle(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/api/v1/cases",
        json={
            "name": "Example investigation",
            "objective": "Map public infrastructure",
            "targets": ["example.com", "Acme Example Labs"],
        },
    )
    assert r.status_code == 201, r.text
    case = r.json()
    assert case["display_id"].startswith("EYO-CASE-")
    assert {t["type"] for t in case["targets"]} == {"DOMAIN", "ORGANIZATION"}
    assert case["targets"][0]["is_primary"] is True
    cid = case["id"]

    # Targets are entities too
    r = await auth_client.get(f"/api/v1/cases/{cid}/entities")
    assert r.json()["total"] == 2
    assert all(e["is_target"] for e in r.json()["items"])

    # Duplicate target rejected with a useful message
    r = await auth_client.post(f"/api/v1/cases/{cid}/targets", json={"value": "EXAMPLE.com"})
    assert r.status_code == 409 and "already exists" in r.json()["message"]

    # Notes extract evidence references
    r = await auth_client.post(
        f"/api/v1/cases/{cid}/notes", json={"body": "Need to verify EYO-EV-000001 against EYO-ENT-000002"}
    )
    assert r.status_code == 201 and r.json()["evidence_refs"] == ["EYO-EV-000001"]

    # Update status and list
    r = await auth_client.patch(f"/api/v1/cases/{cid}", json={"status": "ACTIVE", "priority": "HIGH"})
    assert r.json()["status"] == "ACTIVE"
    r = await auth_client.get("/api/v1/cases", params={"q": "Example"})
    assert any(c["id"] == cid for c in r.json()["items"])

    # Clone keeps targets but not evidence
    r = await auth_client.post(f"/api/v1/cases/{cid}/clone", json={})
    assert r.status_code == 201 and len(r.json()["targets"]) == 2 and r.json()["cloned_from_id"] == cid

    # Lookup by display id works
    r = await auth_client.get(f"/api/v1/cases/{case['display_id']}")
    assert r.status_code == 200

    # Audit log has the actions
    r = await auth_client.get("/api/v1/audit", params={"case_id": cid})
    actions = {a["action"] for a in r.json()["items"]}
    assert {"CASE_CREATED", "TARGET_CREATED", "NOTE_CREATED", "CASE_UPDATED"} <= actions


async def test_viewer_cannot_create_case(client: AsyncClient, auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/api/v1/auth/users",
        json={"email": "viewer@example.com", "username": "viewer1", "password": "ViewerPass123", "role": "viewer"},
    )
    assert r.status_code == 201, r.text
    from httpx import ASGITransport
    from httpx import AsyncClient as AnonClient

    from eyohe.main import app

    async with AnonClient(transport=ASGITransport(app=app), base_url="http://testserver") as v:
        r = await v.post("/api/v1/auth/login", json={"identifier": "viewer1", "password": "ViewerPass123"})
        assert r.status_code == 200
        v.headers["x-csrf-token"] = r.json()["csrf_token"]
        r = await v.post("/api/v1/cases", json={"name": "nope"})
        assert r.status_code == 403
        r = await v.get("/api/v1/cases")
        assert r.status_code == 200
