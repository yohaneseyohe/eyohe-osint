from httpx import AsyncClient


async def test_demo_dataset_is_labelled_and_consistent(auth_client: AsyncClient) -> None:
    from eyohe.core.db import get_session_factory
    from eyohe.services.demo import create_demo_case

    async with get_session_factory()() as db:
        case = await create_demo_case(db)
        await db.commit()
        cid = str(case.id)
    r = await auth_client.get(f"/api/v1/cases/{cid}")
    assert r.json()["is_demo"] is True and "DEMO" in r.json()["name"]
    r = await auth_client.get(f"/api/v1/cases/{cid}/findings")
    findings = r.json()["items"]
    assert all(f["is_demo"] for f in findings)
    identity = next(f for f in findings if f["category"] == "identity")
    assert identity["confidence"] == "POSSIBLE"  # single uncorroborated forum claim, capped
    infra = next(f for f in findings if f["category"] == "infrastructure")
    assert infra["confidence"] == "CORROBORATED"
    r = await auth_client.get(f"/api/v1/cases/{cid}/graph")
    assert r.json()["stats"]["edges"] == 3
    r = await auth_client.get(f"/api/v1/cases/{cid}/timeline")
    assert len(r.json()) == 2
