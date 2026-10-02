"""Persist search queries/results for a case and turn selected results into sources."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from eyohe.core.db import utcnow
from eyohe.core.enums import AuditAction, SourceType
from eyohe.core.errors import NotFoundError
from eyohe.core.security import sha256_text
from eyohe.models.investigations import SearchQuery, SearchResult
from eyohe.search.models import SearchResponse
from eyohe.search.providers import search as run_search
from eyohe.services.audit import record_audit

_SOURCE_TYPE_FOR_DOMAIN = {
    "github.com": SourceType.CODE_REPOSITORY,
    "gitlab.com": SourceType.CODE_REPOSITORY,
    "reddit.com": SourceType.FORUM,
    "news.ycombinator.com": SourceType.FORUM,
    "stackoverflow.com": SourceType.FORUM,
    "twitter.com": SourceType.SOCIAL,
    "x.com": SourceType.SOCIAL,
    "linkedin.com": SourceType.SOCIAL,
    "instagram.com": SourceType.SOCIAL,
    "facebook.com": SourceType.SOCIAL,
    "youtube.com": SourceType.SOCIAL,
    "medium.com": SourceType.WEBSITE,
    "web.archive.org": SourceType.ARCHIVE,
}
_TIER_FOR_DOMAIN = {
    "github.com": 3,
    "gitlab.com": 3,
    "reddit.com": 4,
    "news.ycombinator.com": 4,
    "stackoverflow.com": 4,
    "twitter.com": 4,
    "x.com": 4,
    "instagram.com": 4,
    "facebook.com": 4,
    "youtube.com": 4,
    "linkedin.com": 4,
    "medium.com": 4,
    "wikipedia.org": 2,
    "crunchbase.com": 3,
}
_NEWS_TLDS = (
    "reuters.com",
    "apnews.com",
    "bbc.co.uk",
    "bbc.com",
    "nytimes.com",
    "theguardian.com",
    "wsj.com",
    "bloomberg.com",
    "ft.com",
    "techcrunch.com",
    "wired.com",
    "arstechnica.com",
    "theverge.com",
    "zdnet.com",
    "bleepingcomputer.com",
    "therecord.media",
    "krebsonsecurity.com",
)


def classify_hit(domain: str, category: str, target_domain: str | None = None) -> tuple[SourceType, int, str]:
    if target_domain and (domain == target_domain or domain.endswith("." + target_domain)):
        return SourceType.WEBSITE, 1, "Target's own site: official primary source for statements about itself."
    if domain in _SOURCE_TYPE_FOR_DOMAIN:
        st = _SOURCE_TYPE_FOR_DOMAIN[domain]
        tier = _TIER_FOR_DOMAIN.get(domain, 4)
        return (
            st,
            tier,
            {
                3: "Public technical database/platform record.",
                4: "Community/social content; low reliability until corroborated.",
            }.get(tier, ""),
        )
    if category == "news" or domain in _NEWS_TLDS:
        return (
            SourceType.NEWS,
            2 if domain in _NEWS_TLDS else 3,
            "News publication." if domain in _NEWS_TLDS else "News-category result; publisher reputation not assessed.",
        )
    if category == "documents":
        return SourceType.DOCUMENT, 3, "Public document."
    return SourceType.SEARCH_RESULT, 4, "Search result; reliability not yet assessed."


async def execute_and_store(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    query: str,
    branch: str = "",
    category: str = "general",
    investigation_id: uuid.UUID | None = None,
    task_id: uuid.UUID | None = None,
    max_results: int | None = None,
    providers: list[str] | None = None,
    actor_label: str = "system",
) -> tuple[SearchQuery, list[SearchResult], SearchResponse | None]:
    qh = sha256_text(f"{category}|{query.strip().lower()}")
    sq = SearchQuery(
        case_id=case_id,
        investigation_id=investigation_id,
        task_id=task_id,
        branch=branch,
        query=query,
        provider=",".join(providers or []) or "auto",
        status="RUNNING",
        query_hash=qh,
    )
    session.add(sq)
    await session.flush()
    await record_audit(
        session,
        AuditAction.QUERY_EXECUTED,
        actor_label=actor_label,
        case_id=case_id,
        object_type="search_query",
        object_id=str(sq.id),
        detail={"query": query, "branch": branch},
    )
    try:
        resp = await run_search(query, category=category, max_results=max_results, providers=providers)
    except Exception as exc:
        sq.status = "FAILED"
        sq.error = getattr(exc, "message", str(exc))[:2000]
        sq.executed_at = utcnow()
        await session.flush()
        raise
    sq.status = "COMPLETED"
    sq.provider = resp.provider
    sq.cache_hit = resp.cache_hit
    sq.executed_at = utcnow()
    sq.result_count = len(resp.hits)
    # Skip results already known for this case (same canonical URL) to avoid repeated work.
    known = {
        r
        for (r,) in (
            await session.execute(select(SearchResult.canonical_url).where(SearchResult.case_id == case_id))
        ).all()
    }
    rows: list[SearchResult] = []
    for rank, h in enumerate(resp.hits, 1):
        row = SearchResult(
            query_id=sq.id,
            case_id=case_id,
            created_at=utcnow(),
            rank=rank,
            title=h.title[:2000],
            url=h.url,
            canonical_url=h.canonical_url,
            domain=h.domain,
            snippet=h.snippet[:4000],
            published_at=h.published_at,
            engine=h.engine[:64],
            relevance=h.score,
            result_hash=h.result_hash,
            status="DUPLICATE" if h.canonical_url in known else "NEW",
        )
        session.add(row)
        rows.append(row)
    await session.flush()
    return sq, rows, resp


async def list_queries(
    session: AsyncSession, case_id: uuid.UUID, investigation_id: uuid.UUID | None = None
) -> list[SearchQuery]:
    stmt = select(SearchQuery).where(SearchQuery.case_id == case_id)
    if investigation_id:
        stmt = stmt.where(SearchQuery.investigation_id == investigation_id)
    return list((await session.execute(stmt.order_by(SearchQuery.created_at.desc()))).scalars())


async def list_results(
    session: AsyncSession,
    case_id: uuid.UUID,
    *,
    query_id: uuid.UUID | None = None,
    status: str | None = None,
    limit: int = 200,
) -> list[SearchResult]:
    stmt = select(SearchResult).where(SearchResult.case_id == case_id)
    if query_id:
        stmt = stmt.where(SearchResult.query_id == query_id)
    if status:
        stmt = stmt.where(SearchResult.status == status)
    return list((await session.execute(stmt.order_by(SearchResult.relevance.desc()).limit(limit))).scalars())


async def set_result_status(session: AsyncSession, result_id: uuid.UUID, status: str) -> SearchResult:
    row = await session.get(SearchResult, result_id)
    if row is None:
        raise NotFoundError("Search result not found.")
    row.status = status
    return row


def result_to_dict(r: SearchResult) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "query_id": str(r.query_id),
        "case_id": str(r.case_id),
        "rank": r.rank,
        "title": r.title,
        "url": r.url,
        "canonical_url": r.canonical_url,
        "domain": r.domain,
        "snippet": r.snippet,
        "published_at": r.published_at,
        "collected_at": r.created_at,
        "engine": r.engine,
        "relevance": r.relevance,
        "status": r.status,
        "source_id": str(r.source_id) if r.source_id else None,
    }
