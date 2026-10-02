import httpx
import pytest
import respx

from eyohe.core.errors import ConfigurationError
from eyohe.search.models import SearchHit
from eyohe.search.providers import dedupe_and_rank, search


def test_dedupe_merges_same_page_from_two_engines() -> None:
    hits = [
        SearchHit("A", "https://example.com/page/?utm_source=x", "short", engine="google", score=0.5),
        SearchHit("A", "https://example.com/page", "a much longer snippet here", engine="bing", score=0.4),
        SearchHit("B", "https://other.com/", "", engine="google", score=0.3),
    ]
    out = dedupe_and_rank(hits, 10)
    assert len(out) == 2
    assert out[0].canonical_url == "https://example.com/page"
    assert out[0].snippet == "a much longer snippet here"
    assert "google" in out[0].engine and "bing" in out[0].engine
    assert out[0].score > 0.5  # boosted for multi-engine agreement


@respx.mock
async def test_searxng_provider_parses_and_caches(monkeypatch: pytest.MonkeyPatch) -> None:
    from eyohe.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "search_providers", "searxng")
    monkeypatch.setattr(s, "searxng_url", "http://searx.test:8080")
    route = respx.get("http://searx.test:8080/search").mock(
        return_value=httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.com/a",
                        "title": "A",
                        "content": "snippet a",
                        "engines": ["duckduckgo"],
                        "publishedDate": "2025-01-02",
                    },
                    {"url": "https://example.com/a/", "title": "A", "content": "snippet a again", "engines": ["bing"]},
                    {"url": "https://github.com/x/y", "title": "x/y", "content": "repo", "engines": ["github"]},
                ]
            },
        )
    )
    resp = await search("example.com", max_results=10, use_cache=True)
    assert resp.provider == "searxng" and len(resp.hits) == 2
    assert resp.hits[0].published_at is not None
    resp2 = await search("example.com", max_results=10, use_cache=True)
    assert resp2.cache_hit is True
    assert route.call_count == 1


@respx.mock
async def test_searxng_json_disabled_is_a_configuration_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from eyohe.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "search_providers", "searxng")
    monkeypatch.setattr(s, "searxng_url", "http://searx2.test:8080")
    respx.get("http://searx2.test:8080/search").mock(return_value=httpx.Response(403))
    with pytest.raises(Exception) as exc:
        await search("something unique 123", use_cache=False)
    assert "json" in str(exc.value).lower()


async def test_no_provider_configured_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from eyohe.core.config import get_settings

    s = get_settings()
    monkeypatch.setattr(s, "search_providers", "brave")
    monkeypatch.setattr(s, "brave_api_key", "")
    with pytest.raises(ConfigurationError) as exc:
        await search("anything", use_cache=False)
    assert "BRAVE_API_KEY" in exc.value.message


async def test_blocked_query_rejected_by_api(auth_client) -> None:  # type: ignore[no-untyped-def]
    r = await auth_client.post("/api/v1/search", json={"query": "example.com filetype:env"})
    assert r.status_code == 422 and "refused" in r.json()["message"].lower()
