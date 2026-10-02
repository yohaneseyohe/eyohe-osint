"""Internet Archive (Wayback Machine) CDX API: snapshot history and content-change timeline.
Only metadata is pulled by default; the first and latest snapshot pages are fetched to capture
title changes."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from eyohe.collectors.base import (
    BaseCollector,
    CollectContext,
    CollectorHealth,
    CollectResult,
    EntityItem,
    EvidenceItem,
    SourceItem,
    TimelineItem,
)
from eyohe.core.enums import EntityType, EvidenceType, SourceType, TargetType
from eyohe.core.errors import CollectorError
from eyohe.core.netsafety import SafeHttpClient

CDX = "https://web.archive.org/cdx/search/cdx"


def _ts(ts: str) -> datetime:
    return datetime.strptime(ts[:14].ljust(14, "0"), "%Y%m%d%H%M%S").replace(tzinfo=UTC)


class WaybackCollector(BaseCollector):
    name = "wayback"
    description = "Wayback Machine snapshot history (CDX) with change timeline and title history"
    source_tier = 3
    supported_targets = frozenset({TargetType.DOMAIN, TargetType.URL, TargetType.SOCIAL_ACCOUNT, TargetType.USERNAME})
    stage = "ARCHIVE"

    async def health_check(self) -> CollectorHealth:
        t = time.perf_counter()
        try:
            async with SafeHttpClient(timeout=8) as c:
                r = await c.get(CDX, params={"url": "example.com", "limit": 1, "output": "json"})
            return CollectorHealth(
                self.name,
                "ONLINE" if r.status_code == 200 else "DEGRADED",
                f"CDX HTTP {r.status_code}",
                int((time.perf_counter() - t) * 1000),
            )
        except Exception as exc:
            return CollectorHealth(self.name, "OFFLINE", f"web.archive.org unreachable: {type(exc).__name__}")

    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
        import orjson

        res = CollectResult(collector=self.name)
        if target_type in (TargetType.USERNAME, TargetType.SOCIAL_ACCOUNT):
            platform, _, handle = value.partition(":") if ":" in value else ("", "", value)
            profile_urls = {
                "github": f"github.com/{handle}",
                "reddit": f"reddit.com/user/{handle}",
                "x": f"twitter.com/{handle}",
                "instagram": f"instagram.com/{handle}",
                "tiktok": f"tiktok.com/@{handle}",
                "youtube": f"youtube.com/@{handle}",
                "telegram": f"t.me/{handle}",
            }
            target_url = profile_urls.get(platform, f"github.com/{handle}")
        else:
            target_url = value
        params = {
            "url": target_url,
            "output": "json",
            "fl": "timestamp,original,statuscode,digest,mimetype",
            "collapse": "digest",
            "filter": "statuscode:200",
            "limit": 500,
        }
        async with SafeHttpClient(timeout=45) as c:
            r = await c.get(CDX, params=params)
        if r.status_code == 429 or r.status_code >= 500:
            raise CollectorError(self.name, f"Wayback CDX unavailable (HTTP {r.status_code})", retry_after_seconds=120)
        if r.status_code != 200:
            raise CollectorError(self.name, f"Wayback CDX HTTP {r.status_code}")
        try:
            rows = orjson.loads(r.content) if r.content.strip() else []
        except orjson.JSONDecodeError as exc:
            raise CollectorError(self.name, "CDX returned non-JSON") from exc
        rows = rows[1:] if rows else []
        src_url = f"{CDX}?url={target_url}&output=json"
        res.sources.append(
            SourceItem(
                url=src_url,
                source_type=SourceType.ARCHIVE,
                title=f"Wayback Machine capture index for {target_url}",
                publisher="Internet Archive",
                tier=3,
                reliability_note="Archive index of captured pages; captures reflect what the archive crawler saw at that time.",
                text_content="\n".join(" ".join(x) for x in rows)[:100000],
                content_type="application/json",
            )
        )
        subject = EntityItem(
            EntityType.URL if target_type == TargetType.URL else EntityType.DOMAIN,
            value if target_type in (TargetType.URL, TargetType.DOMAIN) else target_url,
        )
        if not rows:
            res.summary = {"note": f"no Wayback captures for {target_url}"}
            await ctx.log("ARCHIVE", f"No archived captures for {target_url}")
            return res
        first, last = rows[0], rows[-1]
        key = "wb-summary"
        res.evidence.append(
            EvidenceItem(
                claim=f"The Wayback Machine holds {len(rows)} distinct captures of {target_url} between {_ts(first[0]).date()} and {_ts(last[0]).date()}",
                evidence_type=EvidenceType.ARCHIVE_SNAPSHOT,
                excerpt="\n".join(f"{_ts(x[0]).date()} {x[1]} {x[2]}" for x in rows[:40])[:1500],
                source_url=src_url,
                structured={
                    "captures": len(rows),
                    "first": _ts(first[0]).isoformat(),
                    "last": _ts(last[0]).isoformat(),
                },
                entities=[subject],
                collection_method="cdx",
                key=key,
            )
        )
        res.timeline.append(
            TimelineItem(
                occurred_at=_ts(first[0]),
                title=f"First archived capture of {target_url}",
                event_kind="ARCHIVE",
                evidence_key=key,
                entities=[subject],
            )
        )
        # Content-change events: every digest change (collapsed) beyond the first, bounded.
        for x in rows[1 : min(len(rows), 1 + ctx.max_results)]:
            res.timeline.append(
                TimelineItem(
                    occurred_at=_ts(x[0]),
                    title=f"Archived content changed ({target_url})",
                    description=f"capture digest {x[3][:12]}",
                    event_kind="CONTENT_CHANGE",
                    evidence_key=key,
                    entities=[subject],
                )
            )
        # Fetch first and latest capture to record title history (two requests only).
        titles = {}
        for label, row in (("first", first), ("latest", last)):
            cap = f"https://web.archive.org/web/{row[0]}id_/{row[1]}"
            try:
                async with SafeHttpClient(timeout=25, max_bytes=1_500_000) as c:
                    page = await c.get(cap)
                if page.status_code == 200 and "html" in page.content_type:
                    from eyohe.collectors.web_collector import html_to_text

                    title, text, _meta = html_to_text(page.text)
                    titles[label] = title
                    res.sources.append(
                        SourceItem(
                            url=cap,
                            source_type=SourceType.ARCHIVE,
                            title=f"Archived {label} capture ({_ts(row[0]).date()}): {title}"[:300],
                            publisher="Internet Archive",
                            published_at=_ts(row[0]),
                            tier=3,
                            text_content=text,
                            content_type=page.content_type,
                            http_status=page.status_code,
                            raw_content=page.content,
                            metadata={"capture_ts": row[0], "original": row[1]},
                        )
                    )
                    res.evidence.append(
                        EvidenceItem(
                            claim=f"Archived {label} capture of {target_url} on {_ts(row[0]).date()} had title '{title[:120]}'",
                            evidence_type=EvidenceType.ARCHIVE_SNAPSHOT,
                            excerpt=title[:300],
                            source_url=cap,
                            observed_at=_ts(row[0]),
                            structured={"capture_ts": row[0]},
                            entities=[subject],
                            collection_method="wayback_capture",
                            key=f"wb-{label}",
                        )
                    )
            except Exception as exc:
                res.warnings.append(f"could not fetch {label} capture: {type(exc).__name__}")
        if titles.get("first") and titles.get("latest") and titles["first"] != titles["latest"]:
            res.timeline.append(
                TimelineItem(
                    occurred_at=_ts(last[0]),
                    title=f"Page title changed: '{titles['first'][:60]}' → '{titles['latest'][:60]}'",
                    event_kind="TITLE_CHANGE",
                    evidence_key="wb-latest",
                    entities=[subject],
                )
            )
        res.summary = {
            "snapshots": len(rows),
            "first": _ts(first[0]).date().isoformat(),
            "last": _ts(last[0]).date().isoformat(),
        }
        await ctx.log(
            "ARCHIVE",
            f"{len(rows)} archived captures of {target_url} ({res.summary['first']} → {res.summary['last']})",
            **res.summary,
        )
        return res
