"""Controlled tools exposed to the research agent.

Each tool has a Pydantic input schema, a timeout, a per-run call budget, an audit event, and a
permission boundary: the agent can only fetch URLs that previously came back from a tool result
(no free browsing), and it cannot execute shell commands or touch non-public resources."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from eyohe.collectors.base import CollectResult
from eyohe.collectors.registry import collector_registry
from eyohe.core.enums import AuditAction, EntityType, EvidenceType, RelationshipType, TargetType
from eyohe.core.errors import AppError, ConfigurationError
from eyohe.core.urlnorm import normalize_url
from eyohe.models.investigations import InvestigationTask
from eyohe.orchestrator.executors import RunContext
from eyohe.orchestrator.persist import persist_result
from eyohe.services import entities as entity_service
from eyohe.services import evidence as ev_service
from eyohe.services import findings as finding_service
from eyohe.services.audit import record_audit


class SearchWebIn(BaseModel):
    query: str = Field(description="Search query; operators like site:, filetype:, quotes are allowed", max_length=300)
    category: str = Field(default="general", description="general | news | code | social | documents")


class FetchPageIn(BaseModel):
    url: str = Field(description="A URL that appeared in a previous tool result")


class HandleIn(BaseModel):
    handle_or_term: str = Field(description="Username/handle or search term", max_length=200)


class DomainIn(BaseModel):
    domain: str = Field(description="Domain name, e.g. example.com", max_length=253)


class ArchiveIn(BaseModel):
    url_or_domain: str = Field(max_length=500)


class CreateEvidenceIn(BaseModel):
    source_url: str = Field(description="URL of a page fetched earlier in this run")
    claim: str = Field(description="One-sentence factual statement of what the source says", max_length=600)
    excerpt: str = Field(
        description="VERBATIM quote from the fetched page supporting the claim (≤ 400 chars)", max_length=600
    )
    evidence_type: str = Field(
        default="DIRECT_STATEMENT", description="DIRECT_STATEMENT | PUBLIC_STATEMENT | ALLEGATION | TECHNICAL_RECORD"
    )
    entities: list[dict[str, str]] = Field(
        default_factory=list, description="[{type, value}] entities named in the excerpt"
    )


class CreateEntityIn(BaseModel):
    type: str
    value: str = Field(max_length=500)
    evidence_id: str = Field(description="EYO-EV-… id of evidence that mentions this entity")


class CreateRelationshipIn(BaseModel):
    source: dict[str, str] = Field(description="{type, value}")
    target: dict[str, str] = Field(description="{type, value}")
    type: str = Field(
        description="MENTIONS | LINKS_TO | OWNS | AUTHORED | REFERENCES | HOSTED_ON | ASSOCIATED_WITH | POSSIBLY_SAME_ENTITY"
    )
    evidence_ids: list[str] = Field(min_length=1)
    rationale: str = Field(max_length=400)


class VerifyClaimIn(BaseModel):
    claim: str = Field(max_length=600)
    evidence_ids: list[str] = Field(min_length=1, description="EYO-EV-… ids supporting the claim")
    contradicting_ids: list[str] = Field(default_factory=list)
    title: str = Field(max_length=200)
    category: str = Field(default="general")


class FinishIn(BaseModel):
    summary: str = Field(description="Short summary of what was found and what remains unverified", max_length=1500)


@dataclass
class ToolSpec:
    name: str
    description: str
    schema: type[BaseModel]
    handler: Callable[[ToolRuntime, BaseModel], Awaitable[dict[str, Any]]]
    timeout: float = 90.0
    max_calls: int = 10
    stage: str = "AI"

    def to_ollama(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.schema.model_json_schema(),
            },
        }


@dataclass
class ToolRuntime:
    ctx: RunContext
    task: InvestigationTask
    allowed_urls: set[str] = field(default_factory=set)
    fetched_text: dict[str, str] = field(default_factory=dict)  # canonical url -> snapshot text
    calls: dict[str, int] = field(default_factory=dict)
    created_evidence: list[str] = field(default_factory=list)
    created_findings: list[str] = field(default_factory=list)
    discovered: list[str] = field(default_factory=list)

    def allow(self, urls: list[str]) -> None:
        for u in urls:
            try:
                self.allowed_urls.add(normalize_url(u))
            except Exception:  # noqa: S112 - malformed URLs from tool output are simply not allow-listed
                continue


def _summ(result: CollectResult, limit: int = 12) -> dict[str, Any]:
    return {
        "sources": [{"url": s.url, "title": s.title[:120], "tier": s.tier} for s in result.sources[:limit]],
        "evidence": [{"claim": e.claim[:200]} for e in result.evidence[:limit]],
        "entities": sorted(
            {f"{e.type}:{e.value}" for ev in result.evidence for e in ev.entities}
            | {f"{e.type}:{e.value}" for e in result.entities}
        )[:40],
        "warnings": result.warnings[:5],
        **{
            k: v
            for k, v in result.summary.items()
            if k in ("records", "subdomains", "repositories", "posts", "snapshots", "http_status", "title", "note")
        },
    }


async def _run_collector(
    rt: ToolRuntime, name: str, ttype: TargetType, value: str, params: dict[str, Any] | None = None
) -> dict[str, Any]:
    col = collector_registry.get(name)
    if col is None:
        raise ConfigurationError(f"Collector {name} unavailable")
    cctx = rt.ctx.collect_context(rt.task)
    cctx.params = params or {}
    result = await col.collect(cctx, ttype, value)
    result.collector = f"research_agent/{name}"
    stats = await persist_result(rt.ctx.session, rt.ctx.investigation, rt.task, result)
    await rt.ctx.session.commit()
    rt.allow([s.url for s in result.sources])
    for s in result.sources:
        if s.text_content:
            rt.fetched_text[normalize_url(s.url)] = s.text_content
    out = _summ(result)
    out["persisted"] = stats.to_dict()
    out["evidence_ids"] = stats.evidence_ids[:20]
    return out


async def t_search_web(rt: ToolRuntime, inp: BaseModel) -> dict[str, Any]:
    from eyohe.search.providers import search

    assert isinstance(inp, SearchWebIn)
    resp = await search(inp.query, category=inp.category, max_results=10)
    rt.allow([h.url for h in resp.hits])
    return {
        "provider": resp.provider,
        "results": [
            {
                "title": h.title[:120],
                "url": h.url,
                "snippet": h.snippet[:240],
                "domain": h.domain,
                "published_at": h.published_at.isoformat() if h.published_at else None,
            }
            for h in resp.hits
        ],
        "warnings": resp.warnings,
    }


async def t_fetch_page(rt: ToolRuntime, inp: BaseModel) -> dict[str, Any]:
    assert isinstance(inp, FetchPageIn)
    canon = normalize_url(inp.url)
    if canon not in rt.allowed_urls:
        return {
            "error": "URL not in the allowed set. Only URLs returned by search/collector tools in this run may be fetched."
        }
    out = await _run_collector(rt, "web_fetch", TargetType.URL, inp.url)
    text = rt.fetched_text.get(canon, "")
    out["text_preview"] = text[:3000]
    return out


async def t_search_reddit(rt: ToolRuntime, inp: BaseModel) -> dict[str, Any]:
    assert isinstance(inp, HandleIn)
    return await _run_collector(rt, "reddit", TargetType.ORGANIZATION, inp.handle_or_term)


async def t_search_github(rt: ToolRuntime, inp: BaseModel) -> dict[str, Any]:
    assert isinstance(inp, HandleIn)
    return await _run_collector(rt, "github", TargetType.ORGANIZATION, inp.handle_or_term)


async def t_query_dns(rt: ToolRuntime, inp: BaseModel) -> dict[str, Any]:
    assert isinstance(inp, DomainIn)
    return await _run_collector(rt, "dns", TargetType.DOMAIN, inp.domain.lower())


async def t_query_rdap(rt: ToolRuntime, inp: BaseModel) -> dict[str, Any]:
    assert isinstance(inp, DomainIn)
    return await _run_collector(rt, "rdap", TargetType.DOMAIN, inp.domain.lower())


async def t_query_ct(rt: ToolRuntime, inp: BaseModel) -> dict[str, Any]:
    assert isinstance(inp, DomainIn)
    return await _run_collector(rt, "ct_logs", TargetType.DOMAIN, inp.domain.lower())


async def t_search_archive(rt: ToolRuntime, inp: BaseModel) -> dict[str, Any]:
    assert isinstance(inp, ArchiveIn)
    v = inp.url_or_domain
    return await _run_collector(rt, "wayback", TargetType.URL if "://" in v else TargetType.DOMAIN, v)


async def t_create_evidence(rt: ToolRuntime, inp: BaseModel) -> dict[str, Any]:
    """Hallucination guard: the excerpt must be a substring of the fetched page text."""
    assert isinstance(inp, CreateEvidenceIn)
    canon = normalize_url(inp.source_url)
    text = rt.fetched_text.get(canon)
    if text is None:
        return {"error": "source_url was not fetched in this run; call fetch_public_page first."}
    if not ev_service.excerpt_in_text(inp.excerpt, text):
        await record_audit(
            rt.ctx.session,
            AuditAction.AI_QUERY,
            actor_label="research_agent",
            case_id=rt.ctx.case.id,
            detail={"rejected_excerpt": inp.excerpt[:200], "url": canon},
        )
        return {"error": "excerpt not found verbatim in the page text; evidence rejected. Quote the page exactly."}
    try:
        etype = EvidenceType(inp.evidence_type)
    except ValueError:
        etype = EvidenceType.DIRECT_STATEMENT
    if etype not in (
        EvidenceType.DIRECT_STATEMENT,
        EvidenceType.PUBLIC_STATEMENT,
        EvidenceType.ALLEGATION,
        EvidenceType.TECHNICAL_RECORD,
    ):
        etype = EvidenceType.DIRECT_STATEMENT
    session = rt.ctx.session
    src = await ev_service.upsert_source(
        session,
        rt.ctx.case.id,
        url=inp.source_url,
        source_type=__import__("eyohe.core.enums", fromlist=["SourceType"]).SourceType.WEBSITE,
        collector="research_agent",
        tier=4,
    )
    snap = await ev_service.latest_snapshot(session, src.id)
    ev = await ev_service.create_evidence(
        session,
        rt.ctx.case.id,
        claim=inp.claim,
        evidence_type=etype,
        collector="research_agent",
        source=src,
        snapshot=snap,
        excerpt=inp.excerpt,
        investigation_id=rt.ctx.investigation.id,
        collection_method="ai_extraction",
        require_excerpt_in_snapshot=snap is not None,
    )
    ent_ids = []
    for e in inp.entities[:10]:
        try:
            et = EntityType(str(e.get("type", "")).upper())
        except ValueError:
            continue
        val = str(e.get("value", "")).strip()
        if not val or val.lower() not in text.lower():
            continue  # entity must appear in the page
        ent = await entity_service.upsert_entity(session, rt.ctx.case.id, et, val, evidence_id=ev.id)
        ent_ids.append(ent.id)
    if ent_ids:
        await ev_service.link_entities(session, ev, ent_ids)
    await session.commit()
    rt.created_evidence.append(ev.display_id)
    from eyohe.core.enums import EventType
    from eyohe.orchestrator.events import emit_event

    await emit_event(
        session,
        rt.ctx.investigation,
        EventType.EVIDENCE_CREATED,
        "AI",
        f"{ev.display_id}: {ev.claim}"[:300],
        task_id=rt.task.id,
        data={"evidence_id": ev.display_id, "verified_excerpt": ev.excerpt_verified},
    )
    return {"evidence_id": ev.display_id, "excerpt_verified": ev.excerpt_verified, "entities_linked": len(ent_ids)}


async def t_create_entity(rt: ToolRuntime, inp: BaseModel) -> dict[str, Any]:
    assert isinstance(inp, CreateEntityIn)
    try:
        et = EntityType(inp.type.upper())
    except ValueError:
        return {"error": f"unknown entity type {inp.type}"}
    ev = await ev_service.get_evidence(rt.ctx.session, inp.evidence_id)
    hay = (ev.claim + " " + ev.excerpt).lower()
    if inp.value.lower() not in hay:
        return {"error": "entity value does not appear in the cited evidence; rejected."}
    ent = await entity_service.upsert_entity(rt.ctx.session, rt.ctx.case.id, et, inp.value, evidence_id=ev.id)
    await ev_service.link_entities(rt.ctx.session, ev, [ent.id])
    await rt.ctx.session.commit()
    return {"entity_id": ent.display_id}


async def t_create_relationship(rt: ToolRuntime, inp: BaseModel) -> dict[str, Any]:
    assert isinstance(inp, CreateRelationshipIn)
    try:
        rtype = RelationshipType(inp.type.upper())
        st, tt = EntityType(inp.source["type"].upper()), EntityType(inp.target["type"].upper())
    except (ValueError, KeyError):
        return {"error": "invalid relationship or entity type"}
    session = rt.ctx.session
    ev_ids = []
    for eid in inp.evidence_ids[:10]:
        try:
            ev = await ev_service.get_evidence(session, eid)
            ev_ids.append(ev.id)
        except AppError:
            continue
    if not ev_ids:
        return {"error": "no valid evidence ids; relationships require evidence."}
    a = await entity_service.upsert_entity(session, rt.ctx.case.id, st, inp.source["value"], evidence_id=ev_ids[0])
    b = await entity_service.upsert_entity(session, rt.ctx.case.id, tt, inp.target["value"], evidence_id=ev_ids[0])
    rel = await entity_service.create_relationship(
        session,
        rt.ctx.case.id,
        a,
        b,
        rtype,
        evidence_ids=ev_ids,
        rationale=f"[AI proposal] {inp.rationale}",
        attributes={"proposed_by": "research_agent"},
    )
    await session.commit()
    return {
        "relationship_id": rel.display_id,
        "confidence": rel.confidence,
        "note": "identity links stay POSSIBLE until an analyst confirms",
    }


async def t_verify_claim(rt: ToolRuntime, inp: BaseModel) -> dict[str, Any]:
    assert isinstance(inp, VerifyClaimIn)
    session = rt.ctx.session
    sup, con = [], []
    for eid in inp.evidence_ids[:15]:
        try:
            sup.append((await ev_service.get_evidence(session, eid)).id)
        except AppError:
            continue
    for eid in inp.contradicting_ids[:15]:
        try:
            con.append((await ev_service.get_evidence(session, eid)).id)
        except AppError:
            continue
    if not sup and not con:
        return {"error": "no valid evidence ids"}
    f = await finding_service.create_finding(
        session,
        rt.ctx.case.id,
        title=inp.title,
        claim=inp.claim,
        supporting=sup,
        contradicting=con,
        category=inp.category,
        proposed_by="ai",
        investigation_id=rt.ctx.investigation.id,
    )
    await session.commit()
    rt.created_findings.append(f.display_id)
    from eyohe.core.enums import EventType
    from eyohe.orchestrator.events import emit_event

    await emit_event(
        session,
        rt.ctx.investigation,
        EventType.FINDING_CREATED,
        "AI",
        f"{f.display_id} [{f.confidence}] {f.title}"[:300],
        task_id=rt.task.id,
        data={"finding_id": f.display_id, "confidence": f.confidence},
    )
    return {
        "finding_id": f.display_id,
        "computed_confidence": f.confidence,
        "rationale": f.confidence_rationale.get("reasons", []),
    }


async def t_finish(rt: ToolRuntime, inp: BaseModel) -> dict[str, Any]:
    assert isinstance(inp, FinishIn)
    return {"done": True, "summary": inp.summary}


TOOLS: dict[str, ToolSpec] = {
    t.name: t
    for t in (
        ToolSpec(
            "search_web",
            "Search public web/news/code/social/documents via the configured providers.",
            SearchWebIn,
            t_search_web,
            60,
            12,
            "SEARCH",
        ),
        ToolSpec(
            "fetch_public_page",
            "Fetch a public page that appeared in a previous result and return its text preview; stores a snapshot.",
            FetchPageIn,
            t_fetch_page,
            60,
            12,
            "WEB",
        ),
        ToolSpec(
            "search_reddit",
            "Search public Reddit posts for a term or inspect a public user.",
            HandleIn,
            t_search_reddit,
            60,
            3,
            "REDDIT",
        ),
        ToolSpec(
            "search_github",
            "Search public GitHub repositories/users for a term or handle.",
            HandleIn,
            t_search_github,
            60,
            3,
            "GITHUB",
        ),
        ToolSpec("query_dns", "Collect public DNS records for a domain.", DomainIn, t_query_dns, 40, 5, "DNS"),
        ToolSpec("query_rdap", "Collect RDAP registration data for a domain.", DomainIn, t_query_rdap, 40, 5, "RDAP"),
        ToolSpec(
            "query_ct_logs",
            "Collect certificate-transparency hostnames for a domain.",
            DomainIn,
            t_query_ct,
            90,
            3,
            "CT",
        ),
        ToolSpec(
            "search_archive",
            "Collect Wayback Machine capture history for a URL or domain.",
            ArchiveIn,
            t_search_archive,
            90,
            3,
            "ARCHIVE",
        ),
        ToolSpec(
            "create_evidence",
            "Record a claim with a VERBATIM excerpt from a page fetched in this run (rejected if the quote is not in the page).",
            CreateEvidenceIn,
            t_create_evidence,
            30,
            20,
            "AI",
        ),
        ToolSpec(
            "create_entity",
            "Add an entity that appears in cited evidence.",
            CreateEntityIn,
            t_create_entity,
            20,
            20,
            "AI",
        ),
        ToolSpec(
            "create_relationship",
            "Propose an evidence-backed relationship between two entities.",
            CreateRelationshipIn,
            t_create_relationship,
            20,
            15,
            "AI",
        ),
        ToolSpec(
            "verify_claim",
            "Create a finding from evidence ids; confidence is computed by the system, not by you.",
            VerifyClaimIn,
            t_verify_claim,
            20,
            10,
            "VERIFY",
        ),
        ToolSpec(
            "finish",
            "Call when research objectives are met or further searching has diminishing returns.",
            FinishIn,
            t_finish,
            5,
            1,
            "AI",
        ),
    )
}


async def call_tool(rt: ToolRuntime, name: str, raw_args: dict[str, Any]) -> dict[str, Any]:
    spec = TOOLS.get(name)
    if spec is None:
        return {"error": f"unknown tool {name}"}
    n = rt.calls.get(name, 0)
    if n >= spec.max_calls:
        return {"error": f"call budget for {name} exhausted ({spec.max_calls})"}
    rt.calls[name] = n + 1
    try:
        inp = spec.schema.model_validate(raw_args)
    except Exception as exc:
        return {"error": f"invalid arguments: {str(exc)[:300]}"}
    t0 = time.perf_counter()
    try:
        out = await asyncio.wait_for(spec.handler(rt, inp), timeout=spec.timeout)
    except TimeoutError:
        out = {"error": f"{name} timed out after {spec.timeout:.0f}s"}
    except AppError as exc:
        out = {
            "error": exc.message,
            **(
                {"retry_after_seconds": exc.detail.get("retry_after_seconds")}
                if exc.detail.get("retry_after_seconds")
                else {}
            ),
        }
        await rt.ctx.session.rollback()
    except Exception as exc:
        out = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
        await rt.ctx.session.rollback()
    out["_ms"] = int((time.perf_counter() - t0) * 1000)
    await record_audit(
        rt.ctx.session,
        AuditAction.AI_QUERY,
        actor_label="research_agent",
        case_id=rt.ctx.case.id,
        object_type="tool",
        object_id=name,
        detail={"args": {k: (str(v)[:200]) for k, v in raw_args.items()}, "ok": "error" not in out, "ms": out["_ms"]},
    )
    await rt.ctx.session.commit()
    return out


def tool_specs_for_ollama(names: list[str] | None = None) -> list[dict[str, Any]]:
    return [t.to_ollama() for n, t in TOOLS.items() if names is None or n in names]


def investigation_uuid(rt: ToolRuntime) -> uuid.UUID:
    return rt.ctx.investigation.id
