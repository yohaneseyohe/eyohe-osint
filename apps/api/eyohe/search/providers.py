"""Search provider connectors.

A provider is *configured* or it raises ``ConfigurationError``; results are never fabricated.
``search()`` queries providers in the configured priority order, deduplicates by canonical URL,
ranks, and caches. SearXNG is the recommended self-hosted default; Brave, Serper and Tavily are
keyed API connectors.
"""

from __future__ import annotations

import abc
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from dateutil import parser as dateparser

from eyohe.core.config import get_settings
from eyohe.core.errors import CollectorError, ConfigurationError
from eyohe.core.logging import get_logger
from eyohe.core.metrics import search_requests
from eyohe.core.security import sha256_text
from eyohe.search.cache import query_cache
from eyohe.search.models import SearchHit, SearchResponse
from eyohe.search.queries import is_query_allowed
from eyohe.services.health import ComponentHealth

log = get_logger("search")
_CATEGORY_MAP = {
    "general": "general",
    "news": "news",
    "code": "it",
    "social": "social media",
    "documents": "files",
    "images": "images",
}


def _parse_dt(v: Any) -> datetime | None:
    if not v:
        return None
    try:
        d = dateparser.parse(str(v))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except (ValueError, OverflowError, TypeError):
        return None


class SearchProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def configured(self) -> tuple[bool, str]: ...

    @abc.abstractmethod
    async def search(self, query: str, *, category: str, max_results: int) -> list[SearchHit]: ...

    async def health(self) -> tuple[str, str]:
        ok, msg = self.configured()
        return ("ONLINE" if ok else "NOT_CONFIGURED"), msg


class SearXNGProvider(SearchProvider):
    name = "searxng"

    def configured(self) -> tuple[bool, str]:
        return bool(get_settings().searxng_url), "SEARXNG_URL not set"

    async def health(self) -> tuple[str, str]:
        s = get_settings()
        try:
            async with httpx.AsyncClient(timeout=4.0, headers={"User-Agent": s.user_agent}) as c:
                r = await c.get(f"{s.searxng_url.rstrip('/')}/search", params={"q": "eyohe health", "format": "json"})
            if r.status_code == 200:
                return "ONLINE", f"searxng at {s.searxng_url}"
            if r.status_code == 403:
                return "OFFLINE", "searxng: JSON format disabled (add 'json' to search.formats in settings.yml)"
            return "OFFLINE", f"searxng: HTTP {r.status_code}"
        except Exception as exc:
            return (
                "OFFLINE",
                f"searxng unreachable at {s.searxng_url} ({type(exc).__name__}); start it with: docker compose --profile search up -d",
            )

    async def search(self, query: str, *, category: str, max_results: int) -> list[SearchHit]:
        s = get_settings()
        params: dict[str, Any] = {"q": query, "format": "json", "safesearch": 0, "language": "all"}
        if category in _CATEGORY_MAP and category != "general":
            params["categories"] = _CATEGORY_MAP[category]
        hits: list[SearchHit] = []
        pages = 1 if max_results <= 10 else 2
        try:
            async with httpx.AsyncClient(timeout=25.0, headers={"User-Agent": s.user_agent}) as c:
                for page in range(1, pages + 1):
                    r = await c.get(f"{s.searxng_url.rstrip('/')}/search", params={**params, "pageno": page})
                    if r.status_code == 403:
                        raise ConfigurationError(
                            "SearXNG refused JSON output; enable 'json' under search.formats in its settings.yml."
                        )
                    if r.status_code == 429:
                        raise CollectorError("searxng", "rate limited by SearXNG", retry_after_seconds=30)
                    r.raise_for_status()
                    data = r.json()
                    for i, item in enumerate(data.get("results", [])):
                        url = item.get("url")
                        if not url:
                            continue
                        hits.append(
                            SearchHit(
                                title=(item.get("title") or "").strip(),
                                url=url,
                                snippet=(item.get("content") or "").strip(),
                                engine=",".join(item.get("engines", [])) or item.get("engine", ""),
                                provider=self.name,
                                published_at=_parse_dt(item.get("publishedDate")),
                                score=float(item.get("score") or 0) or (1.0 / (i + 1 + (page - 1) * 10)),
                                category=item.get("category", category),
                                extra={"engines": item.get("engines", [])},
                            )
                        )
                    if len(hits) >= max_results or not data.get("results"):
                        break
        except (ConfigurationError, CollectorError):
            raise
        except httpx.HTTPError as exc:
            raise CollectorError(
                "searxng", f"request failed: {type(exc).__name__}: {exc}", impact="search branch skipped"
            ) from exc
        return hits


class BraveProvider(SearchProvider):
    name = "brave"

    def configured(self) -> tuple[bool, str]:
        return bool(get_settings().brave_api_key), "BRAVE_API_KEY not set"

    async def search(self, query: str, *, category: str, max_results: int) -> list[SearchHit]:
        s = get_settings()
        if not s.brave_api_key:
            raise ConfigurationError("Brave Search is not configured (BRAVE_API_KEY missing).")
        endpoint = (
            "https://api.search.brave.com/res/v1/news/search"
            if category == "news"
            else "https://api.search.brave.com/res/v1/web/search"
        )
        try:
            async with httpx.AsyncClient(timeout=20.0) as c:
                r = await c.get(
                    endpoint,
                    params={"q": query, "count": min(max_results, 20)},
                    headers={"X-Subscription-Token": s.brave_api_key, "Accept": "application/json"},
                )
            if r.status_code == 429:
                raise CollectorError(
                    "brave", "API rate limit reached", retry_after_seconds=int(r.headers.get("retry-after", "60"))
                )
            if r.status_code in (401, 403):
                raise ConfigurationError("Brave Search rejected the API key.")
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as exc:
            raise CollectorError("brave", str(exc)) from exc
        items = data.get("results", []) if category == "news" else data.get("web", {}).get("results", [])
        return [
            SearchHit(
                title=i.get("title", ""),
                url=i["url"],
                snippet=i.get("description", ""),
                engine="brave",
                provider=self.name,
                published_at=_parse_dt(i.get("page_age") or i.get("age")),
                score=1.0 / (n + 1),
                category=category,
                extra={"source": (i.get("meta_url") or {}).get("hostname")},
            )
            for n, i in enumerate(items)
            if i.get("url")
        ]


class SerperProvider(SearchProvider):
    name = "serper"

    def configured(self) -> tuple[bool, str]:
        return bool(get_settings().serper_api_key), "SERPER_API_KEY not set"

    async def search(self, query: str, *, category: str, max_results: int) -> list[SearchHit]:
        s = get_settings()
        if not s.serper_api_key:
            raise ConfigurationError("Serper is not configured (SERPER_API_KEY missing).")
        endpoint = "https://google.serper.dev/news" if category == "news" else "https://google.serper.dev/search"
        try:
            async with httpx.AsyncClient(timeout=20.0) as c:
                r = await c.post(
                    endpoint, json={"q": query, "num": min(max_results, 20)}, headers={"X-API-KEY": s.serper_api_key}
                )
            if r.status_code == 429:
                raise CollectorError("serper", "API rate limit reached", retry_after_seconds=60)
            if r.status_code in (401, 403):
                raise ConfigurationError("Serper rejected the API key.")
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as exc:
            raise CollectorError("serper", str(exc)) from exc
        items = data.get("news", []) if category == "news" else data.get("organic", [])
        return [
            SearchHit(
                title=i.get("title", ""),
                url=i["link"],
                snippet=i.get("snippet", ""),
                engine="google",
                provider=self.name,
                published_at=_parse_dt(i.get("date")),
                score=1.0 / (int(i.get("position", n + 1))),
                category=category,
                extra={"source": i.get("source")},
            )
            for n, i in enumerate(items)
            if i.get("link")
        ]


class TavilyProvider(SearchProvider):
    name = "tavily"

    def configured(self) -> tuple[bool, str]:
        return bool(get_settings().tavily_api_key), "TAVILY_API_KEY not set"

    async def search(self, query: str, *, category: str, max_results: int) -> list[SearchHit]:
        s = get_settings()
        if not s.tavily_api_key:
            raise ConfigurationError("Tavily is not configured (TAVILY_API_KEY missing).")
        try:
            async with httpx.AsyncClient(timeout=30.0) as c:
                r = await c.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": s.tavily_api_key,
                        "query": query,
                        "max_results": min(max_results, 20),
                        "topic": "news" if category == "news" else "general",
                        "include_raw_content": False,
                    },
                )
            if r.status_code == 429:
                raise CollectorError("tavily", "API rate limit reached", retry_after_seconds=60)
            if r.status_code in (401, 403):
                raise ConfigurationError("Tavily rejected the API key.")
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as exc:
            raise CollectorError("tavily", str(exc)) from exc
        return [
            SearchHit(
                title=i.get("title", ""),
                url=i["url"],
                snippet=i.get("content", "")[:500],
                engine="tavily",
                provider=self.name,
                published_at=_parse_dt(i.get("published_date")),
                score=float(i.get("score") or 0),
                category=category,
            )
            for i in data.get("results", [])
            if i.get("url")
        ]


PROVIDERS: dict[str, SearchProvider] = {
    p.name: p for p in (SearXNGProvider(), BraveProvider(), SerperProvider(), TavilyProvider())
}


def configured_providers() -> list[SearchProvider]:
    out = []
    for name in get_settings().search_provider_list:
        p = PROVIDERS.get(name)
        if p and p.configured()[0]:
            out.append(p)
    return out


def dedupe_and_rank(hits: list[SearchHit], max_results: int) -> list[SearchHit]:
    """Merge duplicates across engines (same canonical URL), boosting pages found by several."""
    merged: dict[str, SearchHit] = {}
    counts: dict[str, int] = {}
    for h in hits:
        key = h.canonical_url
        counts[key] = counts.get(key, 0) + 1
        if key not in merged:
            merged[key] = h
        else:
            m = merged[key]
            if len(h.snippet) > len(m.snippet):
                m.snippet = h.snippet
            if not m.published_at and h.published_at:
                m.published_at = h.published_at
            if h.engine and h.engine not in m.engine:
                m.engine = f"{m.engine},{h.engine}" if m.engine else h.engine
    for key, h in merged.items():
        h.score = round(h.score + 0.25 * (counts[key] - 1), 4)
    return sorted(merged.values(), key=lambda h: h.score, reverse=True)[:max_results]


async def search(
    query: str,
    *,
    category: str = "general",
    max_results: int | None = None,
    providers: list[str] | None = None,
    use_cache: bool = True,
) -> SearchResponse:
    s = get_settings()
    max_results = max_results or s.max_results_per_source
    ok, why = is_query_allowed(query)
    if not ok:
        raise ConfigurationError(why)
    chosen = (
        [PROVIDERS[p] for p in providers if p in PROVIDERS and PROVIDERS[p].configured()[0]]
        if providers
        else configured_providers()
    )
    if not chosen:
        problems = [
            f"{PROVIDERS[n].name}: {PROVIDERS[n].configured()[1]}" for n in s.search_provider_list if n in PROVIDERS
        ] or ["SEARCH_PROVIDERS is empty"]
        raise ConfigurationError(
            "No search provider is configured. "
            + "; ".join(problems)
            + ". Start SearXNG (docker compose --profile search up -d) or add an API key in .env."
        )
    key = sha256_text(f"{category}|{max_results}|{','.join(p.name for p in chosen)}|{query.strip().lower()}")
    if use_cache:
        cached = await query_cache.get(key)
        if cached:
            search_requests.labels(provider="cache", cache="hit").inc()
            hits = [SearchHit(**{**h, "published_at": _parse_dt(h.get("published_at"))}) for h in cached["hits"]]
            return SearchResponse(query=query, provider=cached["provider"], hits=hits, cache_hit=True)
    t0 = time.perf_counter()
    all_hits: list[SearchHit] = []
    warnings: list[str] = []
    used: list[str] = []
    for p in chosen:
        try:
            hits = await p.search(query, category=category, max_results=max_results)
            search_requests.labels(provider=p.name, cache="miss").inc()
            all_hits.extend(hits)
            used.append(p.name)
            if len(all_hits) >= max_results:
                break
        except ConfigurationError as exc:
            warnings.append(exc.message)
        except CollectorError as exc:
            warnings.append(exc.message)
            log.warning("search_provider_failed", provider=p.name, error=exc.message)
    if not used:
        raise CollectorError(
            "search", "all configured providers failed: " + "; ".join(warnings), impact="search branch skipped"
        )
    ranked = dedupe_and_rank(all_hits, max_results)
    resp = SearchResponse(
        query=query,
        provider=",".join(used),
        hits=ranked,
        elapsed_ms=int((time.perf_counter() - t0) * 1000),
        warnings=warnings,
    )
    if use_cache:
        await query_cache.set(
            key,
            {
                "provider": resp.provider,
                "hits": [
                    {
                        "title": h.title,
                        "url": h.url,
                        "snippet": h.snippet,
                        "engine": h.engine,
                        "provider": h.provider,
                        "published_at": h.published_at.isoformat() if h.published_at else None,
                        "score": h.score,
                        "category": h.category,
                        "extra": h.extra,
                    }
                    for h in ranked
                ],
            },
        )
    return resp


async def provider_health() -> ComponentHealth:
    s = get_settings()
    t = time.perf_counter()
    configured: list[str] = []
    problems: list[str] = []
    for name in s.search_provider_list:
        p = PROVIDERS.get(name)
        if p is None:
            problems.append(f"unknown provider '{name}'")
            continue
        status, msg = await p.health()
        (configured if status == "ONLINE" else problems).append(name if status == "ONLINE" else msg)
    status = (
        "ONLINE"
        if configured and not problems
        else ("DEGRADED" if configured else ("NOT_CONFIGURED" if not s.search_provider_list else "OFFLINE"))
    )
    msg = (f"ready: {', '.join(configured)}" if configured else "") + (
        (" | " if configured else "") + "; ".join(problems) if problems else ""
    )
    return ComponentHealth(
        "search",
        status,
        msg or "no providers configured",
        int((time.perf_counter() - t) * 1000),
        {"configured": configured, "problems": problems},
        optional=False,
    )
