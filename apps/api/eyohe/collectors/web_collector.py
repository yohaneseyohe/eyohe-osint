"""Public web page fetcher: title, meta, visible text, outbound links, technology hints, contacts.
Fetches through the SSRF-safe client; never submits forms, never authenticates, never evades
anti-bot measures (a 403/429 is recorded as 'not publicly retrievable')."""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from eyohe.collectors.base import (
    BaseCollector,
    CollectContext,
    CollectorHealth,
    CollectResult,
    EntityItem,
    EvidenceItem,
    RelationshipItem,
    SourceItem,
)
from eyohe.core.enums import EntityType, EvidenceType, RelationshipType, SourceType, TargetType
from eyohe.core.errors import CollectorError
from eyohe.core.netsafety import SafeHttpClient
from eyohe.core.urlnorm import normalize_url, registrable_domain
from eyohe.enrichment.extract import extract_entities

_TECH_HINTS = {
    "wordpress": re.compile(r"wp-content|wp-includes|wordpress", re.I),
    "drupal": re.compile(r"drupal", re.I),
    "joomla": re.compile(r"joomla", re.I),
    "shopify": re.compile(r"cdn\.shopify\.com|shopify", re.I),
    "next.js": re.compile(r"_next/static|__NEXT_DATA__", re.I),
    "nuxt": re.compile(r"_nuxt/", re.I),
    "react": re.compile(r"react(-dom)?(\.production)?\.min\.js|data-reactroot", re.I),
    "vue": re.compile(r"vue(\.min)?\.js|data-v-", re.I),
    "angular": re.compile(r"ng-version=", re.I),
    "jquery": re.compile(r"jquery[.-]", re.I),
    "bootstrap": re.compile(r"bootstrap(\.min)?\.(css|js)", re.I),
    "cloudflare": re.compile(r"cdn-cgi/|cloudflare", re.I),
    "google analytics": re.compile(r"googletagmanager\.com|google-analytics\.com|gtag\(", re.I),
    "hubspot": re.compile(r"js\.hs-scripts\.com|hubspot", re.I),
    "squarespace": re.compile(r"squarespace", re.I),
    "wix": re.compile(r"wix\.com|wixstatic", re.I),
    "webflow": re.compile(r"webflow", re.I),
    "ghost": re.compile(r"ghost\.io|content=\"Ghost", re.I),
    "hugo": re.compile(r"content=\"Hugo", re.I),
    "gatsby": re.compile(r"gatsby", re.I),
}


def html_to_text(html: str) -> tuple[str, str, dict[str, Any]]:
    soup = BeautifulSoup(html, "lxml")
    for t in soup(["script", "style", "noscript", "svg", "template"]):
        t.decompose()
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else ""
    meta: dict[str, Any] = {}
    for m in soup.find_all("meta"):
        name = str(m.get("name") or m.get("property") or "").lower()
        content = m.get("content")
        if (
            name
            and content
            and name
            in (
                "description",
                "author",
                "generator",
                "og:title",
                "og:site_name",
                "og:description",
                "og:type",
                "twitter:site",
                "twitter:creator",
                "article:published_time",
                "article:modified_time",
                "keywords",
                "application-name",
            )
        ):
            meta[name] = str(content)[:500]
    canonical = soup.find("link", rel=lambda v: v and "canonical" in v)
    if canonical and canonical.get("href"):
        meta["canonical"] = str(canonical["href"])[:500]
    text = soup.get_text("\n")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return title, text, meta


class WebFetchCollector(BaseCollector):
    name = "web_fetch"
    description = "Fetch a public web page: title, text, metadata, outbound links, technology hints, contacts"
    source_tier = 4
    supported_targets = frozenset({TargetType.DOMAIN, TargetType.URL})
    stage = "WEB"

    async def health_check(self) -> CollectorHealth:
        t = time.perf_counter()
        try:
            async with SafeHttpClient(timeout=6) as c:
                r = await c.get("https://www.example.com/")
            return CollectorHealth(
                self.name,
                "ONLINE" if r.status_code < 500 else "DEGRADED",
                f"HTTP {r.status_code}",
                int((time.perf_counter() - t) * 1000),
            )
        except Exception as exc:
            return CollectorHealth(self.name, "OFFLINE", f"outbound HTTP failed: {type(exc).__name__}")

    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
        res = CollectResult(collector=self.name)
        candidates = [value] if target_type == TargetType.URL else [f"https://{value}/", f"http://{value}/"]
        fetched = None
        last_err = ""
        async with SafeHttpClient(timeout=25) as c:
            for url in candidates:
                try:
                    fetched = await c.get(
                        url,
                        headers={
                            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
                            "Accept-Language": "en",
                        },
                    )
                    break
                except Exception as exc:
                    last_err = f"{type(exc).__name__}: {exc}"
        if fetched is None:
            raise CollectorError(self.name, f"could not fetch {value}: {last_err[:200]}", impact="no page evidence")
        url = fetched.final_url
        domain = registrable_domain(url)
        is_target_site = target_type == TargetType.DOMAIN or domain == registrable_domain(value)
        tier = 1 if is_target_site and target_type == TargetType.DOMAIN else 4
        if fetched.status_code in (401, 403, 429, 451):
            res.sources.append(
                SourceItem(
                    url=url,
                    source_type=SourceType.WEBSITE,
                    title=f"{value} (HTTP {fetched.status_code})",
                    tier=tier,
                    http_status=fetched.status_code,
                    content_type=fetched.content_type,
                    reliability_note="Page not publicly retrievable without interaction; no bypass attempted.",
                )
            )
            res.evidence.append(
                EvidenceItem(
                    claim=f"{url} responded with HTTP {fetched.status_code}; content is not publicly retrievable by an automated client (not verified further)",
                    evidence_type=EvidenceType.TECHNICAL_RECORD,
                    source_url=url,
                    structured={"http_status": fetched.status_code},
                    entities=[EntityItem(EntityType.URL, url)],
                    collection_method="http_get",
                )
            )
            res.summary = {"http_status": fetched.status_code, "note": "not publicly retrievable"}
            return res
        ct = fetched.content_type.split(";")[0].strip().lower()
        if ct == "application/pdf" or fetched.content[:5] == b"%PDF-":
            return self._document_result(
                ctx, res, url, fetched.content, "application/pdf", fetched.status_code, fetched.elapsed_ms
            )
        if ct in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ):
            return self._document_result(ctx, res, url, fetched.content, ct, fetched.status_code, fetched.elapsed_ms)
        html = fetched.text
        title, text, meta = html_to_text(html)
        src = SourceItem(
            url=url,
            source_type=SourceType.WEBSITE,
            title=title or url,
            publisher=meta.get("og:site_name", ""),
            author=meta.get("author", ""),
            tier=tier,
            reliability_note="Target's own public website (primary source for its own statements)."
            if tier == 1
            else "Third-party public page.",
            text_content=text,
            raw_content=fetched.content if len(fetched.content) <= 3_000_000 else None,
            content_type=fetched.content_type or "text/html",
            http_status=fetched.status_code,
            final_url=url,
            fetch_ms=fetched.elapsed_ms,
            truncated=fetched.truncated,
            metadata={
                **meta,
                "headers": {
                    k: v
                    for k, v in fetched.headers.items()
                    if k in ("server", "x-powered-by", "content-type", "last-modified", "x-generator", "via", "cf-ray")
                },
            },
        )
        res.sources.append(src)
        page_entity = EntityItem(EntityType.URL, normalize_url(url))
        domain_entity = EntityItem(EntityType.DOMAIN, domain)
        key = "page"
        res.evidence.append(
            EvidenceItem(
                claim=f"Public page {url} (HTTP {fetched.status_code}) has title '{title[:150]}'"
                + (f" and description '{meta['description'][:150]}'" if meta.get("description") else ""),
                evidence_type=EvidenceType.TECHNICAL_RECORD,
                excerpt=(title + "\n" + meta.get("description", ""))[:600],
                source_url=url,
                structured={"http_status": fetched.status_code, "meta": meta},
                entities=[page_entity, domain_entity],
                collection_method="http_get",
                key=key,
            )
        )
        tech = sorted({name for name, pat in _TECH_HINTS.items() if pat.search(html[:400_000])})
        server = fetched.headers.get("server", "")
        powered = fetched.headers.get("x-powered-by", "")
        if meta.get("generator"):
            tech.append(f"generator: {meta['generator'][:60]}")
        if tech or server or powered:
            tech_entities = [
                EntityItem(EntityType.TECHNOLOGY, t.split(":")[-1].strip(), attributes={"evidence": "page markup"})
                for t in tech[:10]
            ]
            res.evidence.append(
                EvidenceItem(
                    claim=f"Technology indicators on {url}: {', '.join(tech) or 'none in markup'}"
                    + (f"; Server header: {server}" if server else "")
                    + (f"; X-Powered-By: {powered}" if powered else ""),
                    evidence_type=EvidenceType.TECHNICAL_RECORD,
                    excerpt=f"server={server} x-powered-by={powered} indicators={','.join(tech)}"[:500],
                    source_url=url,
                    structured={"technologies": tech, "server": server, "x_powered_by": powered},
                    entities=[domain_entity, *tech_entities],
                    collection_method="fingerprint",
                    key="tech",
                )
            )
            for te in tech_entities:
                res.relationships.append(
                    RelationshipItem(
                        domain_entity,
                        te,
                        RelationshipType.REFERENCES,
                        rationale="technology indicator in public page markup",
                        evidence_keys=["tech"],
                    )
                )
        links: dict[str, str] = {}
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = urljoin(url, str(a["href"]).strip())
            if href.startswith(("http://", "https://")):
                try:
                    h = urlsplit(href).hostname or ""
                except ValueError:
                    continue
                if h and registrable_domain(h) != domain:
                    links.setdefault(normalize_url(href), (a.get_text(" ", strip=True) or "")[:100])
        ents = extract_entities(
            text
            + "\n"
            + "\n".join(links)
            + "\n"
            + "\n".join(f"mailto:{a['href'][7:]}" for a in soup.find_all("a", href=re.compile(r"^mailto:", re.I)))
        )
        socials = [e for e in ents if e.type == EntityType.SOCIAL_ACCOUNT]
        emails = [e for e in ents if e.type == EntityType.EMAIL]
        ext_domains = sorted({registrable_domain(u) for u in links})[:40]
        if links:
            res.evidence.append(
                EvidenceItem(
                    claim=f"{url} links out to {len(links)} external URLs across {len(ext_domains)} domains"
                    + (
                        f", including public social profiles: {', '.join(s.value for s in socials[:8])}"
                        if socials
                        else ""
                    ),
                    evidence_type=EvidenceType.TECHNICAL_RECORD,
                    excerpt="\n".join(list(links)[:40])[:1500],
                    source_url=url,
                    structured={"external_links": list(links)[:200], "external_domains": ext_domains},
                    entities=[
                        domain_entity,
                        *socials[:15],
                        *[EntityItem(EntityType.DOMAIN, d) for d in ext_domains[:15]],
                    ],
                    collection_method="link_extraction",
                    key="links",
                )
            )
            for s_ in socials[:15]:
                res.relationships.append(
                    RelationshipItem(
                        domain_entity,
                        s_,
                        RelationshipType.LINKS_TO,
                        rationale="profile link on the public page",
                        evidence_keys=["links"],
                    )
                )
        if emails:
            res.evidence.append(
                EvidenceItem(
                    claim=f"Public contact addresses on {url}: {', '.join(e.value for e in emails[:10])}",
                    evidence_type=EvidenceType.DIRECT_STATEMENT,
                    excerpt=", ".join(e.value for e in emails[:10]),
                    source_url=url,
                    structured={"emails": [e.value for e in emails[:20]]},
                    entities=[domain_entity, *emails[:20]],
                    collection_method="contact_extraction",
                    key="emails",
                )
            )
            for e in emails[:20]:
                res.relationships.append(
                    RelationshipItem(
                        domain_entity,
                        e,
                        RelationshipType.MENTIONS,
                        rationale="address published on the page",
                        evidence_keys=["emails"],
                    )
                )
        for s_ in socials:
            res.discovered_targets.append((TargetType.SOCIAL_ACCOUNT, s_.value))
        res.summary = {
            "http_status": fetched.status_code,
            "title": title[:120],
            "external_links": len(links),
            "technologies": tech[:10],
            "emails": len(emails),
            "social_links": len(socials),
            "text_chars": len(text),
        }
        await ctx.log(
            "WEB",
            f"Fetched {url} ({fetched.status_code}): '{title[:80]}' — {len(links)} external links, {len(socials)} social profiles",
            **{k: v for k, v in res.summary.items() if k != "title"},
        )
        return res

    def _document_result(
        self, ctx: CollectContext, res: CollectResult, url: str, content: bytes, mime: str, status: int, ms: int
    ) -> CollectResult:
        from eyohe.enrichment.documents import extract_document

        info = extract_document(content, mime)
        src = SourceItem(
            url=url,
            source_type=SourceType.DOCUMENT,
            title=info.title or url.rsplit("/", 1)[-1],
            author=info.author,
            published_at=info.created_at,
            tier=3,
            reliability_note="Public document; metadata fields are self-reported by the authoring software and may be inaccurate.",
            text_content=info.text,
            raw_content=content if len(content) <= 5_000_000 else None,
            content_type=mime,
            http_status=status,
            final_url=url,
            fetch_ms=ms,
            metadata={
                "document": {
                    "author": info.author,
                    "creator": info.creator,
                    "producer": info.producer,
                    "pages": info.pages,
                    "created": info.created_at.isoformat() if info.created_at else None,
                    "modified": info.modified_at.isoformat() if info.modified_at else None,
                }
            },
        )
        res.sources.append(src)
        doc_entity = EntityItem(EntityType.DOCUMENT, normalize_url(url), label=info.title or url.rsplit("/", 1)[-1])
        ents = [doc_entity]
        if info.author:
            ents.append(
                EntityItem(
                    EntityType.PERSON
                    if len(info.author.split()) <= 4 and "@" not in info.author
                    else EntityType.ORGANIZATION,
                    info.author,
                    attributes={"from": "document metadata", "caveat": "metadata author field; not identity-verified"},
                )
            )
        text_ents = extract_entities(info.text[:50_000])
        claim = (
            f"Public document at {url} ({mime.split('/')[-1]}, {info.pages or '?'} pages)"
            + (f" has metadata author '{info.author}'" if info.author else " has no author metadata")
            + (f", created {info.created_at.date()}" if info.created_at else "")
            + (f", modified {info.modified_at.date()}" if info.modified_at else "")
        )
        res.evidence.append(
            EvidenceItem(
                claim=claim,
                evidence_type=EvidenceType.DOCUMENT,
                excerpt=(info.title + "\n" + info.text[:800]).strip()[:1000],
                source_url=url,
                observed_at=info.created_at,
                structured={
                    "metadata": info.metadata,
                    "pages": info.pages,
                    "creator": info.creator,
                    "producer": info.producer,
                    "warnings": info.warnings,
                },
                entities=[*ents, *text_ents[:20]],
                collection_method="document_extraction",
                key="doc",
            )
        )
        if len(ents) > 1:
            res.relationships.append(
                RelationshipItem(
                    ents[1],
                    doc_entity,
                    RelationshipType.AUTHORED,
                    rationale="document metadata author field (not identity-verified)",
                    evidence_keys=["doc"],
                )
            )
        for w in info.warnings:
            res.warnings.append(w)
        res.summary = {"document": mime, "pages": info.pages, "author": info.author, "entities": len(text_ents)}
        return res
