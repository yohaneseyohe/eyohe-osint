from httpx import AsyncClient


async def test_setup_then_login_and_csrf(client: AsyncClient) -> None:
    r = await client.get("/api/v1/auth/setup")
    assert r.status_code == 200
    from tests.conftest import ADMIN

    if r.json()["needs_setup"]:
        r = await client.post("/api/v1/auth/setup", json=ADMIN)
        assert r.status_code == 201
        # second setup must be refused
        r2 = await client.post("/api/v1/auth/setup", json=ADMIN)
        assert r2.status_code == 409
    r = await client.post("/api/v1/auth/login", json={"identifier": "admin", "password": "wrong-password-1A"})
    assert r.status_code == 401
    assert "Invalid" in r.json()["message"]
    r = await client.post("/api/v1/auth/login", json={"identifier": "admin", "password": ADMIN["password"]})
    assert r.status_code == 200
    csrf = r.json()["csrf_token"]
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 200 and me.json()["user"]["role"] == "admin"
    # unsafe method without CSRF header is rejected
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 403
    client.headers["x-csrf-token"] = csrf
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 200
    me = await client.get("/api/v1/auth/me")
    assert me.status_code == 401


async def test_weak_password_rejected(auth_client: AsyncClient) -> None:
    r = await auth_client.post(
        "/api/v1/auth/users",
        json={"email": "weak@example.test", "username": "weak", "password": "alllowercase1", "role": "viewer"},
    )
    assert r.status_code == 422
    assert "upper and lower" in r.json()["message"]


async def test_api_token_bearer(auth_client: AsyncClient) -> None:
    r = await auth_client.post("/api/v1/auth/tokens", params={"name": "ci"})
    assert r.status_code == 201
    token = r.json()["token"]
    assert token.startswith("eyo_")
    from httpx import ASGITransport
    from httpx import AsyncClient as AnonClient

    from eyohe.main import app

    async with AnonClient(transport=ASGITransport(app=app), base_url="http://testserver") as anon:
        r = await anon.get("/api/v1/auth/me", headers={"authorization": f"Bearer {token}"})
        assert r.status_code == 200
        r = await anon.get("/api/v1/auth/me", headers={"authorization": "Bearer eyo_bogus"})
        assert r.status_code == 401
