import asyncio

from httpx import AsyncClient


async def test_sse_stream_survives_idle_heartbeat(auth_client: AsyncClient) -> None:
    """Regression: the heartbeat timeout must not kill the live subscription."""
    from eyohe.orchestrator.events import event_bus

    r = await auth_client.post("/api/v1/cases", json={"name": "SSE", "targets": ["example.com"]})
    cid = r.json()["id"]
    r = await auth_client.post(
        "/api/v1/investigations/start", json={"case_id": cid, "request_text": "x", "use_ai": False}
    )
    inv = r.json()
    received: list[dict] = []  # type: ignore[type-arg]

    async def consume() -> None:
        async with event_bus.subscription(inv["id"]) as q:
            for _ in range(3):
                try:
                    received.append(await asyncio.wait_for(q.get(), timeout=0.2))
                except TimeoutError:
                    continue  # heartbeat path: subscription must still be alive afterwards
            received.append(await asyncio.wait_for(q.get(), timeout=5))

    task = asyncio.create_task(consume())
    await asyncio.sleep(0.8)  # let the timeouts fire first
    await event_bus.publish({"investigation_id": inv["id"], "seq": 999, "message": "late event"})
    await asyncio.wait_for(task, timeout=6)
    assert any(e.get("seq") == 999 for e in received)
    # Replay endpoint still returns persisted events in order
    r = await auth_client.get(f"/api/v1/investigations/{inv['id']}/events")
    assert [e["seq"] for e in r.json()] == sorted(e["seq"] for e in r.json())
