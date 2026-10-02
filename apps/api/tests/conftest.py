"""Test fixtures: isolated SQLite database per test session, HTTP client, authenticated client."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("EYOHE_ENV", "test")
os.environ.setdefault("LOG_JSON", "false")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("JOB_BACKEND", "embedded")
os.environ.setdefault("AUTH_RATE_LIMIT_PER_MINUTE", "10000")
os.environ.setdefault("RATE_LIMIT_PER_MINUTE", "100000")


@pytest.fixture(scope="session")
def tmp_data_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    d = tmp_path_factory.mktemp("eyohe-data")
    os.environ["DATA_DIR"] = str(d)
    if not os.environ.get("EYOHE_PG_TEST"):  # EYOHE_PG_TEST=1 keeps DATABASE_URL (PostgreSQL) as given
        os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{d / 'test.sqlite3'}"
    from eyohe.core.config import get_settings

    get_settings.cache_clear()
    return d


@pytest.fixture(scope="session", autouse=True)
async def _schema(tmp_data_dir: Path) -> AsyncIterator[None]:
    import eyohe.models  # noqa: F401 - register tables
    from eyohe.core.db import Base, get_engine, reset_engine_for_tests

    reset_engine_for_tests(os.environ["DATABASE_URL"])
    engine = get_engine()
    async with engine.begin() as conn:
        if os.environ.get("EYOHE_PG_TEST"):
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from eyohe.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


ADMIN = {
    "email": "admin@example.test",
    "username": "admin",
    "password": "CorrectHorse9Battery",
    "display_name": "Admin",
}


@pytest.fixture
async def auth_client(client: AsyncClient) -> AsyncClient:
    """Client signed in as the admin (created via first-run setup if needed)."""
    r = await client.get("/api/v1/auth/setup")
    if r.json()["needs_setup"]:
        r = await client.post("/api/v1/auth/setup", json=ADMIN)
        assert r.status_code == 201, r.text
    else:
        r = await client.post(
            "/api/v1/auth/login", json={"identifier": ADMIN["username"], "password": ADMIN["password"]}
        )
        assert r.status_code == 200, r.text
    client.headers["x-csrf-token"] = r.json()["csrf_token"]
    return client
