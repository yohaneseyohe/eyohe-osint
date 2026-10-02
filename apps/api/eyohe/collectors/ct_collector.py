"""Certificate transparency via crt.sh. Reveals publicly issued certificates and hostnames
(subdomains) without touching the target's infrastructure."""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import UTC, datetime

from dateutil import parser as dateparser

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
from eyohe.core.enums import EntityType, EvidenceType, RelationshipType, SourceType, TargetType
from eyohe.core.errors import CollectorError
from eyohe.core.netsafety import SafeHttpClient


class CTLogCollector(BaseCollector):
    name = "ct_logs"
    description = "Certificate transparency search (crt.sh): issued certificates, issuers, subdomains"
    source_tier = 3
    supported_targets = frozenset({TargetType.DOMAIN, TargetType.EMAIL, TargetType.URL})
    stage = "CT"

    async def health_check(self) -> CollectorHealth:
        t = time.perf_counter()
        try:
            async with SafeHttpClient(timeout=8) as c:
                r = await c.get("https://crt.sh/", params={"q": "example.com", "output": "json"})
            return CollectorHealth(
                self.name,
                "ONLINE" if r.status_code == 200 else "DEGRADED",
                f"crt.sh HTTP {r.status_code}",
                int((time.perf_counter() - t) * 1000),
            )
        except Exception as exc:
            return CollectorHealth(self.name, "OFFLINE", f"crt.sh unreachable: {type(exc).__name__}")

    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
        import orjson

        from eyohe.core.urlnorm import host_of, registrable_domain

        host = (
            value.split("@")[-1]
            if target_type == TargetType.EMAIL
            else (host_of(value) if target_type == TargetType.URL else value)
        )
        domain = registrable_domain(host) or host
        res = CollectResult(collector=self.name)
        url = f"https://crt.sh/?q=%25.{domain}&output=json"
        async with SafeHttpClient(timeout=60, max_bytes=20_000_000) as c:
            r = await c.get(url)
        if r.status_code == 429 or r.status_code >= 500:
            raise CollectorError(
                self.name,
                f"crt.sh unavailable (HTTP {r.status_code}); it is a free public service and is often busy",
                retry_after_seconds=120,
                impact="no certificate evidence",
            )
        if r.status_code != 200:
            raise CollectorError(self.name, f"crt.sh HTTP {r.status_code}")
        try:
            rows = orjson.loads(r.content) if r.content.strip() else []
        except orjson.JSONDecodeError as exc:
            raise CollectorError(
                self.name, "crt.sh returned non-JSON (probably overloaded)", retry_after_seconds=120
            ) from exc
        src = SourceItem(
            url=url,
            source_type=SourceType.TECHNICAL_RECORD,
            title=f"Certificate transparency results for {domain}",
            publisher="crt.sh",
            tier=3,
            reliability_note="Public CT log aggregator; proves a certificate was logged, not that a host is live.",
            text_content=r.text[:200000],
            content_type="application/json",
            http_status=200,
            raw_content=r.content if len(r.content) < 5_000_000 else None,
        )
        res.sources.append(src)
        names: dict[str, dict[str, datetime | None]] = defaultdict(lambda: {"first": None, "last": None})
        issuers: dict[str, int] = defaultdict(int)
        for row in rows:
            for n in str(row.get("name_value", "")).split("\n"):
                n = n.strip().lower().lstrip("*.")
                if not n or not (n == domain or n.endswith("." + domain)):
                    continue
                d = _dt(row.get("not_before"))
                e = _dt(row.get("not_after"))
                rec = names[n]
                if d and (rec["first"] is None or d < rec["first"]):
                    rec["first"] = d
                if e and (rec["last"] is None or e > rec["last"]):
                    rec["last"] = e
            issuers[str(row.get("issuer_name", ""))[:160]] += 1
        domain_entity = EntityItem(EntityType.DOMAIN, domain)
        key = "ct-summary"
        subs = sorted(n for n in names if n != domain)
        res.evidence.append(
            EvidenceItem(
                claim=f"Certificate transparency logs contain {len(rows)} certificate entries for {domain} covering {len(names)} hostnames ({len(subs)} subdomains); top issuers: {', '.join(i for i, _ in sorted(issuers.items(), key=lambda x: -x[1])[:3])[:200]}",
                evidence_type=EvidenceType.TECHNICAL_RECORD,
                excerpt="\n".join(subs[:60])[:1500],
                source_url=url,
                structured={
                    "certificates": len(rows),
                    "hostnames": len(names),
                    "subdomains": subs[:500],
                    "issuers": dict(sorted(issuers.items(), key=lambda x: -x[1])[:10]),
                },
                entities=[
                    domain_entity,
                    *[
                        EntityItem(EntityType.DOMAIN, s, attributes={"from": "ct_logs"})
                        for s in subs[: ctx.max_results * 5]
                    ],
                ],
                collection_method="crt.sh",
                key=key,
            )
        )
        for s in subs[: ctx.max_results * 5]:
            res.relationships.append(
                RelationshipItem(
                    EntityItem(EntityType.DOMAIN, s),
                    domain_entity,
                    RelationshipType.SUBDOMAIN_OF,
                    rationale="hostname appears in a logged certificate",
                    evidence_keys=[key],
                )
            )
        earliest = min((v["first"] for v in names.values() if v["first"]), default=None)
        if earliest:
            res.timeline.append(
                TimelineItem(
                    occurred_at=earliest,
                    title=f"Earliest logged certificate for {domain}",
                    description="First not_before date across CT entries",
                    event_kind="CERTIFICATE",
                    evidence_key=key,
                    entities=[domain_entity],
                )
            )
        res.summary = {"records": len(rows), "subdomains": len(subs), "hostnames": len(names)}
        await ctx.log("CT", f"{len(rows)} CT entries, {len(subs)} subdomains for {domain}", **res.summary)
        return res


def _dt(v: object) -> datetime | None:
    if not v:
        return None
    try:
        d = dateparser.parse(str(v))
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except (ValueError, TypeError, OverflowError):
        return None
