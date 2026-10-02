"""Reddit public JSON endpoints (no API key): search, public user profiles and submissions.
Everything is treated as community discussion (tier 4): statements are recorded as
PUBLIC_STATEMENT / ALLEGATION, never as facts."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import orjson

from eyohe.collectors.base import (
    BaseCollector,
    CollectContext,
    CollectorHealth,
    CollectResult,
    EntityItem,
    EvidenceItem,
    RelationshipItem,
    SourceItem,
    TimelineItem,
)
from eyohe.core.config import get_settings
from eyohe.core.enums import EntityType, EvidenceType, RelationshipType, SourceType, TargetType
from eyohe.core.errors import CollectorError
from eyohe.core.netsafety import SafeHttpClient
from eyohe.enrichment.extract import extract_entities

BASE = "https://www.reddit.com"
_ALLEGATION_HINTS = (
    "scam",
    "fraud",
    "fake",
    "stole",
    "hacked",
    "breach",
    "lawsuit",
    "sued",
    "illegal",
    "malware",
    "phishing",
)


def _ts(v: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(v), tz=UTC) if v else None
    except (TypeError, ValueError, OSError):
        return None


class RedditCollector(BaseCollector):
    name = "reddit"
    description = "Public Reddit search, user profiles and submissions (public JSON, no login)"
    source_tier = 4
    supported_targets = frozenset(
        {
            TargetType.DOMAIN,
            TargetType.USERNAME,
            TargetType.SOCIAL_ACCOUNT,
            TargetType.ORGANIZATION,
            TargetType.COMPANY,
            TargetType.PERSON,
            TargetType.EMAIL,
            TargetType.CRYPTO_ADDRESS,
            TargetType.IP,
        }
    )
    stage = "REDDIT"

    def _headers(self) -> dict[str, str]:
        return {"User-Agent": get_settings().reddit_user_agent, "Accept": "application/json"}

    async def health_check(self) -> CollectorHealth:
        t = time.perf_counter()
        try:
            async with SafeHttpClient(timeout=8) as c:
                r = await c.get(f"{BASE}/r/announcements/about.json", headers=self._headers())
            if r.status_code == 200:
                return CollectorHealth(
                    self.name, "ONLINE", "public JSON reachable", int((time.perf_counter() - t) * 1000)
                )
            if r.status_code in (403, 429):
                return CollectorHealth(
                    self.name,
                    "DEGRADED",
                    f"Reddit returned HTTP {r.status_code} (rate limited or blocked for this network; no bypass attempted)",
                )
            return CollectorHealth(self.name, "DEGRADED", f"HTTP {r.status_code}")
        except Exception as exc:
            return CollectorHealth(self.name, "OFFLINE", f"reddit unreachable: {type(exc).__name__}")

    async def _json(self, c: SafeHttpClient, path: str, params: dict[str, Any] | None = None) -> Any:
        r = await c.get(f"{BASE}{path}", params=params, headers=self._headers())
        if r.status_code == 429:
            raise CollectorError(
                self.name,
                "Reddit rate limit reached",
                retry_after_seconds=int(r.headers.get("retry-after", "60") or 60),
                impact="Reddit task incomplete",
            )
        if r.status_code == 403:
            raise CollectorError(
                self.name,
                "Reddit refused the request (HTTP 403). Public JSON is sometimes blocked for datacenter networks; no bypass is attempted.",
                retry_after_seconds=600,
            )
        if r.status_code == 404:
            return None
        if r.status_code >= 400:
            raise CollectorError(self.name, f"Reddit HTTP {r.status_code}")
        try:
            return orjson.loads(r.content)
        except orjson.JSONDecodeError as exc:
            raise CollectorError(self.name, "Reddit returned non-JSON (likely a block page)") from exc

    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
        res = CollectResult(collector=self.name)
        handle = ctx.params.get("handle") or (
            value.split(":", 1)[1] if target_type == TargetType.SOCIAL_ACCOUNT and value.startswith("reddit:") else None
        )
        async with SafeHttpClient(timeout=25, min_interval=1.2) as c:
            if target_type in (TargetType.USERNAME, TargetType.SOCIAL_ACCOUNT):
                await self._user(ctx, c, res, handle or value.split(":", 1)[-1])
            term = value.split(":", 1)[-1] if target_type == TargetType.SOCIAL_ACCOUNT else value
            await self._search(ctx, c, res, term)
        await ctx.log(
            "REDDIT",
            f"Reddit: {res.summary.get('posts', 0)} public posts"
            + (" (profile found)" if res.summary.get("profile") else ""),
            **res.summary,
        )
        return res

    async def _user(self, ctx: CollectContext, c: SafeHttpClient, res: CollectResult, handle: str) -> None:
        about = await self._json(c, f"/user/{handle}/about.json")
        if not about or not about.get("data") or about["data"].get("is_suspended"):
            res.summary["profile"] = False
            res.warnings.append(f"No public Reddit account 'u/{handle}' (not publicly verifiable).")
            return
        d = about["data"]
        url = f"{BASE}/user/{d.get('name', handle)}"
        acct = EntityItem(
            EntityType.SOCIAL_ACCOUNT,
            f"reddit:{d.get('name', handle).lower()}",
            label=f"u/{d.get('name', handle)}",
            attributes={"platform": "reddit", "handle": d.get("name"), "url": url},
        )
        created = _ts(d.get("created_utc"))
        sub = d.get("subreddit") or {}
        res.sources.append(
            SourceItem(
                url=url,
                source_type=SourceType.SOCIAL,
                title=f"Reddit profile u/{d.get('name')}",
                publisher="Reddit",
                published_at=created,
                tier=4,
                reliability_note="Platform profile record; bio is self-declared.",
                text_content=orjson.dumps(d).decode()[:20000],
                content_type="application/json",
                http_status=200,
            )
        )
        bio = (sub.get("public_description") or "").strip()
        res.evidence.append(
            EvidenceItem(
                claim=f"Public Reddit account u/{d.get('name')} exists; created {created.date() if created else 'unknown'}; link karma {d.get('link_karma', 0)}, comment karma {d.get('comment_karma', 0)}"
                + (f"; public bio: {bio[:160]}" if bio else ""),
                evidence_type=EvidenceType.TECHNICAL_RECORD,
                excerpt=bio[:400],
                source_url=url,
                observed_at=created,
                structured={
                    "created_utc": d.get("created_utc"),
                    "link_karma": d.get("link_karma"),
                    "comment_karma": d.get("comment_karma"),
                    "verified": d.get("verified"),
                },
                entities=[acct, *extract_entities(bio)[:10]],
                collection_method="reddit_about",
                key="rd-profile",
            )
        )
        if created:
            res.timeline.append(
                TimelineItem(
                    occurred_at=created,
                    title=f"Reddit account u/{d.get('name')} created",
                    description="created_utc from the public profile",
                    event_kind="ACCOUNT_CREATED",
                    evidence_key="rd-profile",
                    entities=[acct],
                )
            )
        posts = await self._json(
            c, f"/user/{handle}/submitted.json", {"limit": min(ctx.max_results, 25), "sort": "new"}
        )
        n = 0
        for child in (posts or {}).get("data", {}).get("children", []):
            self._post_item(res, child.get("data", {}), acct, author_known=True)
            n += 1
        res.summary["profile"] = True
        res.summary["posts"] = res.summary.get("posts", 0) + n

    async def _search(self, ctx: CollectContext, c: SafeHttpClient, res: CollectResult, term: str) -> None:
        q = f'"{term}"' if " " in term or "." in term else term
        data = await self._json(
            c, "/search.json", {"q": q, "limit": min(ctx.max_results, 25), "sort": "relevance", "type": "link"}
        )
        n = 0
        for child in (data or {}).get("data", {}).get("children", []):
            self._post_item(res, child.get("data", {}), None, author_known=False)
            n += 1
        res.summary["posts"] = res.summary.get("posts", 0) + n

    def _post_item(self, res: CollectResult, p: dict[str, Any], acct: EntityItem | None, *, author_known: bool) -> None:
        permalink = p.get("permalink") or ""
        url = f"{BASE}{permalink}" if permalink.startswith("/") else (p.get("url") or "")
        if not url:
            return
        author = p.get("author") or "[deleted]"
        created = _ts(p.get("created_utc"))
        title = (p.get("title") or "")[:300]
        body = (p.get("selftext") or "")[:1500]
        subreddit = p.get("subreddit", "")
        author_entity = acct or (
            EntityItem(
                EntityType.SOCIAL_ACCOUNT,
                f"reddit:{author.lower()}",
                label=f"u/{author}",
                attributes={"platform": "reddit", "handle": author},
            )
            if author not in ("[deleted]", "AutoModerator")
            else None
        )
        text = f"{title}\n{body}"
        is_allegation = any(h in text.lower() for h in _ALLEGATION_HINTS)
        key = f"rd-post-{p.get('id', url)}"
        res.sources.append(
            SourceItem(
                url=url,
                source_type=SourceType.FORUM,
                title=f"r/{subreddit}: {title}",
                publisher="Reddit",
                author=f"u/{author}",
                published_at=created,
                tier=4,
                reliability_note="Community discussion; low reliability until corroborated.",
                text_content=text,
                content_type="text/plain",
                http_status=200,
                metadata={
                    "subreddit": subreddit,
                    "score": p.get("score"),
                    "num_comments": p.get("num_comments"),
                    "link_url": p.get("url"),
                },
            )
        )
        date_s = created.date().isoformat() if created else "an unknown date"
        claim = (
            f"According to a Reddit post in r/{subreddit} published on {date_s}, a user identified as u/{author} "
            + ("alleged" if is_allegation else "stated")
            + f': "{title[:160]}"'
        )
        ents = [e for e in extract_entities(text) if e.type != EntityType.USERNAME][:12]
        if author_entity:
            ents.insert(0, author_entity)
        res.evidence.append(
            EvidenceItem(
                claim=claim,
                evidence_type=EvidenceType.ALLEGATION if is_allegation else EvidenceType.PUBLIC_STATEMENT,
                excerpt=text[:1000],
                source_url=url,
                observed_at=created,
                structured={
                    "subreddit": subreddit,
                    "author": author,
                    "score": p.get("score"),
                    "num_comments": p.get("num_comments"),
                    "post_id": p.get("id"),
                    "direct_statement": True,
                },
                entities=ents,
                collection_method="reddit_json",
                key=key,
            )
        )
        if author_entity:
            post_entity = EntityItem(
                EntityType.ARTICLE,
                url,
                label=title[:120] or url,
                attributes={"platform": "reddit", "subreddit": subreddit},
            )
            res.relationships.append(
                RelationshipItem(
                    author_entity,
                    post_entity,
                    RelationshipType.AUTHORED,
                    rationale="post author field in Reddit's public JSON",
                    evidence_keys=[key],
                )
            )
        if created:
            res.timeline.append(
                TimelineItem(
                    occurred_at=created,
                    title=f"Reddit post in r/{subreddit}: {title[:80]}",
                    event_kind="PUBLIC_POST",
                    evidence_key=key,
                    entities=[author_entity] if author_entity else [],
                )
            )
