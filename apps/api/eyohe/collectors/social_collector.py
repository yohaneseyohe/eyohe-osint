"""Public social-profile presence check.

For a handle, we request the public profile URL on each platform exactly like a browser would,
once, and record only what is publicly observable: whether a page exists (HTTP 200 with the
handle in the title/metadata), its public title/description, and public links. Platforms that
require login or return 403/429 are recorded as "not publicly verifiable". No evasion."""

from __future__ import annotations

import time

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
from eyohe.core.netsafety import SafeHttpClient
from eyohe.enrichment.extract import extract_entities

PLATFORMS: dict[str, str] = {
    "github": "https://github.com/{h}",
    "reddit": "https://www.reddit.com/user/{h}/",
    "x": "https://x.com/{h}",
    "instagram": "https://www.instagram.com/{h}/",
    "tiktok": "https://www.tiktok.com/@{h}",
    "youtube": "https://www.youtube.com/@{h}",
    "telegram": "https://t.me/{h}",
    "mastodon.social": "https://mastodon.social/@{h}",
    "gitlab": "https://gitlab.com/{h}",
    "keybase": "https://keybase.io/{h}",
    "medium": "https://medium.com/@{h}",
    "devto": "https://dev.to/{h}",
    "hackernews": "https://news.ycombinator.com/user?id={h}",
    "pinterest": "https://www.pinterest.com/{h}/",
    "twitch": "https://www.twitch.tv/{h}",
    "steam": "https://steamcommunity.com/id/{h}",
    "linktree": "https://linktr.ee/{h}",
    "about.me": "https://about.me/{h}",
    "pypi": "https://pypi.org/user/{h}/",
    "npm": "https://www.npmjs.com/~{h}",
}
# Platforms whose "not found" page still returns 200; require the handle in the title.
_SOFT_404 = {"x", "instagram", "tiktok", "youtube", "telegram", "pinterest", "steam", "linktree", "about.me"}


class SocialProfileCollector(BaseCollector):
    name = "social_profiles"
    description = "Public profile presence check across major platforms for a handle (public pages only)"
    source_tier = 4
    supported_targets = frozenset({TargetType.USERNAME, TargetType.SOCIAL_ACCOUNT})
    stage = "SOCIAL"

    async def health_check(self) -> CollectorHealth:
        t = time.perf_counter()
        try:
            async with SafeHttpClient(timeout=6) as c:
                r = await c.get("https://t.me/telegram")
            return CollectorHealth(
                self.name,
                "ONLINE" if r.status_code < 500 else "DEGRADED",
                f"HTTP {r.status_code}",
                int((time.perf_counter() - t) * 1000),
            )
        except Exception as exc:
            return CollectorHealth(self.name, "OFFLINE", f"outbound HTTP failed: {type(exc).__name__}")

    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
        from eyohe.collectors.web_collector import html_to_text

        handle = ctx.params.get("handle") or value.split(":", 1)[-1]
        handle = handle.lstrip("@")
        res = CollectResult(collector=self.name)
        username = EntityItem(EntityType.USERNAME, handle)
        found: list[str] = []
        unverifiable: list[str] = []
        absent: list[str] = []
        async with SafeHttpClient(timeout=15, max_bytes=1_000_000, min_interval=0.3) as c:
            for platform, tpl in PLATFORMS.items():
                url = tpl.format(h=handle)
                try:
                    r = await c.get(url, headers={"Accept": "text/html,*/*;q=0.8", "Accept-Language": "en"})
                except Exception as exc:
                    unverifiable.append(f"{platform} ({type(exc).__name__})")
                    continue
                if r.status_code in (401, 403, 429, 451, 999):
                    unverifiable.append(f"{platform} (HTTP {r.status_code})")
                    continue
                if r.status_code == 404 or r.status_code >= 500:
                    absent.append(platform)
                    continue
                if r.status_code != 200 or "html" not in r.content_type:
                    unverifiable.append(f"{platform} (HTTP {r.status_code})")
                    continue
                title, text, meta = html_to_text(r.text)
                blob = f"{title} {meta.get('og:title', '')} {meta.get('description', '')} {meta.get('og:description', '')}".lower()
                if platform in _SOFT_404 and handle.lower() not in blob and handle.lower() not in r.final_url.lower():
                    absent.append(platform)
                    continue
                if (
                    any(
                        x in blob
                        for x in (
                            "page not found",
                            "doesn't exist",
                            "does not exist",
                            "not found",
                            "isn't available",
                            "profile unavailable",
                        )
                    )
                    and handle.lower() not in blob
                ):
                    absent.append(platform)
                    continue
                found.append(platform)
                acct = EntityItem(
                    EntityType.SOCIAL_ACCOUNT,
                    f"{platform}:{handle.lower()}",
                    label=f"{handle} ({platform})",
                    attributes={"platform": platform, "handle": handle, "url": r.final_url},
                )
                desc = meta.get("og:description") or meta.get("description") or ""
                key = f"social-{platform}"
                res.sources.append(
                    SourceItem(
                        url=r.final_url,
                        source_type=SourceType.SOCIAL,
                        title=title or f"{platform} profile {handle}",
                        publisher=platform,
                        tier=4,
                        reliability_note="Public profile page; displayed details are self-declared by the account holder.",
                        text_content=text[:30000],
                        raw_content=r.content if len(r.content) < 800_000 else None,
                        content_type=r.content_type,
                        http_status=200,
                        final_url=r.final_url,
                        fetch_ms=r.elapsed_ms,
                        metadata=meta,
                    )
                )
                ents = [
                    acct,
                    username,
                    *[
                        e
                        for e in extract_entities(desc + "\n" + text[:5000])
                        if e.type in (EntityType.URL, EntityType.DOMAIN, EntityType.EMAIL, EntityType.SOCIAL_ACCOUNT)
                        and e.value != acct.value
                    ][:10],
                ]
                res.evidence.append(
                    EvidenceItem(
                        claim=f"A public {platform} profile page exists for handle '{handle}' at {r.final_url} with title '{title[:120]}'"
                        + (f"; public description: {desc[:140]}" if desc else ""),
                        evidence_type=EvidenceType.TECHNICAL_RECORD,
                        excerpt=(title + "\n" + desc)[:600],
                        source_url=r.final_url,
                        structured={
                            "platform": platform,
                            "title": title[:300],
                            "description": desc[:500],
                            "meta": {
                                k: v
                                for k, v in meta.items()
                                if k in ("og:title", "og:description", "description", "twitter:site")
                            },
                        },
                        entities=ents,
                        collection_method="public_profile_page",
                        key=key,
                    )
                )
                res.relationships.append(
                    RelationshipItem(
                        username,
                        acct,
                        RelationshipType.ASSOCIATED_WITH,
                        rationale="same handle; profile page publicly reachable (identity NOT confirmed — different people can share a handle)",
                        evidence_keys=[key],
                    )
                )
                for e in ents[2:]:
                    if e.type in (EntityType.URL, EntityType.DOMAIN):
                        res.relationships.append(
                            RelationshipItem(
                                acct,
                                e,
                                RelationshipType.LINKS_TO,
                                rationale="link in public profile metadata",
                                evidence_keys=[key],
                            )
                        )
        if unverifiable:
            res.warnings.append("Not publicly verifiable (login wall / rate limit): " + ", ".join(unverifiable))
        res.summary = {"found": found, "absent": absent, "unverifiable": unverifiable, "records": len(found)}
        await ctx.log(
            "SOCIAL",
            f"Handle '{handle}': public profile pages on {len(found)} platform(s)"
            + (f" ({', '.join(found)})" if found else "")
            + f"; {len(unverifiable)} not publicly verifiable",
            **res.summary,
        )
        return res
