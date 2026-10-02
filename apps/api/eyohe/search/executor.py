"""Executors for search-driven tasks: search_web, search_news, documents.

Each branch is executed (bounded by MAX_QUERIES), results are stored, the most relevant new pages
are fetched through the web_fetch collector (bounded by MAX_PAGES) and turned into sources,
snapshots, evidence and entities with provenance.
"""

from __future__ import annotations

from typing import Any

from eyohe.collectors.base import CollectResult, EvidenceItem, SourceItem
from eyohe.core.enums import EvidenceType, TargetType
from eyohe.core.errors import CollectorError, ConfigurationError
from eyohe.core.urlnorm import registrable_domain
from eyohe.enrichment.extract import extract_entities
from eyohe.models.investigations import InvestigationTask
from eyohe.orchestrator.executors import RunContext, register_executor
from eyohe.orchestrator.persist import persist_result
from eyohe.search.queries import QueryBranch, generate_branches
from eyohe.search.service import classify_hit, execute_and_store

_FETCH_SKIP_DOMAINS = {
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
}  # login-walled; never bypass


async def _run_branches(
    ctx: RunContext, task: InvestigationTask, branches: list[QueryBranch], *, fetch_pages: bool
) -> dict[str, Any]:
    session, inv = ctx.session, ctx.investigation
    ttype, value = ctx.task_target(task)
    target_domain = (
        value if ttype == TargetType.DOMAIN else (value.split("@")[-1] if ttype == TargetType.EMAIL else None)
    )
    max_queries = int(ctx.bounds.get("max_queries", 40))
    max_pages = int(ctx.bounds.get("max_pages", 60))
    used_queries = int(inv.stats.get("queries_used", 0))
    pages_used = int(inv.stats.get("pages_used", 0))
    stats: dict[str, Any] = {
        "queries": 0,
        "results": 0,
        "new_results": 0,
        "sources": 0,
        "evidence": 0,
        "entities": 0,
        "warnings": [],
    }
    result = CollectResult(collector="search")
    to_fetch: list[tuple[str, str, str]] = []  # (url, title, branch)
    for b in branches:
        if used_queries >= max_queries:
            stats["warnings"].append(f"MAX_QUERIES ({max_queries}) reached; remaining branches skipped")
            break
        await ctx.collect_context(task).log(
            "SEARCH", f"Query [{b.name}]: {b.query}", query=b.query, branch=b.name, category=b.category
        )
        try:
            _sq, rows, resp = await execute_and_store(
                session,
                ctx.case.id,
                query=b.query,
                branch=b.name,
                category=b.category,
                investigation_id=inv.id,
                task_id=task.id,
                max_results=int(ctx.bounds.get("max_results_per_source", 20)),
            )
        except ConfigurationError:
            raise
        except CollectorError as exc:
            stats["warnings"].append(exc.message)
            continue
        used_queries += 1
        stats["queries"] += 1
        stats["results"] += len(rows)
        new_rows = [r for r in rows if r.status == "NEW"]
        stats["new_results"] += len(new_rows)
        await ctx.collect_context(task).log(
            "SEARCH",
            f"{len(rows)} public results ({len(new_rows)} new) via {resp.provider if resp else '?'}"
            + (" [cache]" if resp and resp.cache_hit else ""),
            count=len(rows),
            new=len(new_rows),
        )
        for r in new_rows:
            st, tier, note = classify_hit(r.domain, b.category, target_domain)
            result.sources.append(
                SourceItem(
                    url=r.url,
                    source_type=st,
                    title=r.title,
                    published_at=r.published_at,
                    tier=tier,
                    reliability_note=note,
                    metadata={"engine": r.engine, "query": b.query, "branch": b.name, "rank": r.rank},
                )
            )
            if r.snippet:
                ents = extract_entities(f"{r.title}\n{r.snippet}\n{r.url}")
                result.evidence.append(
                    EvidenceItem(
                        claim=f"Public page '{r.title or r.domain}' is returned for query {b.query!r} and mentions the target context",
                        evidence_type=EvidenceType.PUBLIC_STATEMENT
                        if st in ("FORUM", "SOCIAL")
                        else EvidenceType.TECHNICAL_RECORD,
                        excerpt=r.snippet[:1000],
                        source_url=r.url,
                        observed_at=r.published_at,
                        structured={"query": b.query, "rank": r.rank, "engine": r.engine, "category": b.category},
                        entities=[e for e in ents if e.type.value != "DOMAIN" or e.value != r.domain][:15],
                        collection_method="search_snippet",
                    )
                )
            if fetch_pages and registrable_domain(r.url) not in _FETCH_SKIP_DOMAINS and r.rank <= 5:
                to_fetch.append((r.url, r.title, b.name))
    p = await persist_result(session, inv, task, result)
    stats["sources"] += p.sources
    stats["evidence"] += p.evidence
    stats["entities"] += p.entities
    inv.stats = {**inv.stats, "queries_used": used_queries}
    await session.commit()
    if fetch_pages and to_fetch:
        from eyohe.collectors.registry import collector_registry

        fetcher = collector_registry.get("web_fetch")
        fetched = 0
        for url, _title, branch in to_fetch:
            if pages_used >= max_pages:
                stats["warnings"].append(f"MAX_PAGES ({max_pages}) reached; remaining pages not fetched")
                break
            if fetcher is None:
                break
            try:
                cctx = ctx.collect_context(task)
                cctx.params = {"branch": branch, "reason": "search result"}
                res = await fetcher.collect(cctx, TargetType.URL, url)
                res.collector = "search"
                pr = await persist_result(session, inv, task, res)
                stats["sources"] += pr.new_sources
                stats["evidence"] += pr.evidence
                stats["entities"] += pr.new_entities
                fetched += 1
                pages_used += 1
                inv.stats = {**inv.stats, "pages_used": pages_used}
                await session.commit()
            except Exception as exc:
                stats["warnings"].append(f"fetch failed for {url}: {getattr(exc, 'message', str(exc))[:160]}")
                await session.rollback()
        stats["pages_fetched"] = fetched
    stats["warnings"] = stats["warnings"][:20]
    if not stats["queries"]:
        stats["note"] = "no queries executed"
    return stats


@register_executor("search_web")
async def search_web_executor(ctx: RunContext, task: InvestigationTask) -> dict[str, Any]:
    ttype, value = ctx.task_target(task)
    custom = task.params.get("branches")
    if isinstance(custom, list) and custom:
        branches = [QueryBranch(name=f"branch {i + 1}", query=str(q), category="general") for i, q in enumerate(custom)]
    else:
        branches = generate_branches(ttype, value, objective=ctx.investigation.objective)
    branches = [b for b in branches if b.category != "news"]
    return await _run_branches(ctx, task, branches, fetch_pages=True)


@register_executor("search_news")
async def search_news_executor(ctx: RunContext, task: InvestigationTask) -> dict[str, Any]:
    _ttype, value = ctx.task_target(task)
    q = f'"{value}"' if " " in value or "." in value else value
    branches = [
        QueryBranch("News", q, "news"),
        QueryBranch("News: announcements", f"{q} (announces OR launches OR acquires OR breach OR lawsuit)", "news"),
    ]
    return await _run_branches(ctx, task, branches, fetch_pages=True)


@register_executor("documents")
async def documents_executor(ctx: RunContext, task: InvestigationTask) -> dict[str, Any]:
    _ttype, value = ctx.task_target(task)
    q = f'"{value}"' if " " in value or "." in value else value
    branches = [
        QueryBranch("PDF documents", f"{q} filetype:pdf", "documents"),
        QueryBranch("Office documents", f"{q} (filetype:docx OR filetype:xlsx OR filetype:pptx)", "documents"),
    ]
    return await _run_branches(ctx, task, branches, fetch_pages=True)
