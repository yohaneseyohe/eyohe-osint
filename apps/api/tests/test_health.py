from httpx import AsyncClient


async def test_health_shape(client: AsyncClient) -> None:
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    names = {c["name"] for c in body["components"]}
    assert {"api", "database", "redis", "ollama", "search", "collectors", "graph", "storage", "internet"} <= names
    db = next(c for c in body["components"] if c["name"] == "database")
    assert db["status"] == "ONLINE"


async def test_security_headers_and_request_id(client: AsyncClient) -> None:
    r = await client.get("/api/v1/health/live")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-request-id"]
