from httpx import AsyncClient


async def test_evidence_entity_relationship_finding_and_why(auth_client: AsyncClient) -> None:
    r = await auth_client.post("/api/v1/cases", json={"name": "Evidence chain", "targets": ["example.com"]})
    cid = r.json()["id"]
    domain_entity = r.json()["targets"][0]["entity_id"]

    r = await auth_client.post(
        f"/api/v1/cases/{cid}/evidence",
        json={
            "claim": "The website lists Acme Example Labs as the operator",
            "evidence_type": "DIRECT_STATEMENT",
            "source_url": "https://example.com/about",
            "excerpt": "operated by Acme Example Labs",
        },
    )
    assert r.status_code == 201, r.text
    ev1 = r.json()
    assert ev1["display_id"].startswith("EYO-EV-") and ev1["source"]["display_id"].startswith("EYO-SRC-")
    assert ev1["confidence"] == "POSSIBLE"  # manual source tier 5

    r = await auth_client.post(
        f"/api/v1/cases/{cid}/entities",
        json={"type": "ORGANIZATION", "value": "Acme Example Labs", "evidence_id": ev1["id"]},
    )
    org = r.json()
    assert org["display_id"].startswith("EYO-ENT-")

    # Relationship without evidence is refused
    r = await auth_client.post(
        f"/api/v1/cases/{cid}/relationships",
        json={"source_entity_id": org["id"], "target_entity_id": domain_entity, "type": "OWNS", "evidence_ids": []},
    )
    assert r.status_code == 422

    r = await auth_client.post(
        f"/api/v1/cases/{cid}/relationships",
        json={
            "source_entity_id": org["id"],
            "target_entity_id": domain_entity,
            "type": "OWNS",
            "evidence_ids": [ev1["id"]],
            "rationale": "Stated on the about page",
        },
    )
    assert r.status_code == 201, r.text
    rel = r.json()
    assert rel["why"]["chain"][0]["evidence_id"] == ev1["display_id"]
    assert rel["confidence"] == "POSSIBLE"

    # Graph contains both nodes and the evidence-backed edge
    r = await auth_client.get(f"/api/v1/cases/{cid}/graph")
    g = r.json()
    assert g["stats"]["nodes"] == 2 and g["stats"]["edges"] == 1 and g["edges"][0]["evidence_count"] == 1

    # Finding + Why
    r = await auth_client.post(
        f"/api/v1/cases/{cid}/findings",
        json={
            "title": "Domain operated by Acme Example Labs",
            "claim": "example.com is operated by Acme Example Labs",
            "supporting": [ev1["id"]],
            "category": "infrastructure",
        },
    )
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["confidence"] == "POSSIBLE"
    r = await auth_client.get(f"/api/v1/findings/{f['id']}/why")
    why = r.json()
    assert why["chain"][0]["source"]["url"] == "https://example.com/about"
    assert "Single source" in why["reasoning"]

    # Analyst rejects the evidence → finding becomes CONTRADICTED after re-verification
    r = await auth_client.post(
        f"/api/v1/evidence/{ev1['id']}/review", json={"state": "REJECTED", "note": "page does not say this"}
    )
    assert r.json()["review_state"] == "REJECTED"
    r = await auth_client.get(f"/api/v1/findings/{f['id']}")
    assert r.json()["confidence"] == "UNVERIFIED"  # rejected evidence is excluded → nothing left

    # Timeline is empty but endpoint works; evidence list filters work
    r = await auth_client.get(f"/api/v1/cases/{cid}/timeline")
    assert r.status_code == 200
    r = await auth_client.get(f"/api/v1/cases/{cid}/evidence", params={"review_state": "REJECTED"})
    assert r.json()["total"] == 1
