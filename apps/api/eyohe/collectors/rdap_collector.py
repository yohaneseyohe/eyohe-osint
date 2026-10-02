"""RDAP (the structured successor to WHOIS) via the IANA bootstrap service rdap.org for domains
and IP addresses. Registration events become timeline items."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

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

_EVENT_TITLES = {
    "registration": "Domain registered",
    "expiration": "Registration expires",
    "last changed": "Registration last changed",
    "last update of rdap database": None,
    "transfer": "Domain transferred",
    "reregistration": "Domain re-registered",
}


def _dt(v: str) -> datetime | None:
    try:
        d = dateparser.parse(v)
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except (ValueError, TypeError, OverflowError):
        return None


def _vcard_name(entity: dict[str, Any]) -> str:
    for item in entity.get("vcardArray", [None, []])[1] or []:
        if item and item[0] == "fn" and len(item) > 3 and item[3]:
            return str(item[3])
    return str(entity.get("handle", ""))


class RDAPCollector(BaseCollector):
    name = "rdap"
    description = "RDAP registration data for domains and IP networks (registrar, dates, nameservers, status)"
    source_tier = 3
    supported_targets = frozenset({TargetType.DOMAIN, TargetType.IP, TargetType.EMAIL, TargetType.URL})
    stage = "RDAP"

    async def health_check(self) -> CollectorHealth:
        t = time.perf_counter()
        try:
            async with SafeHttpClient(timeout=6) as c:
                r = await c.get("https://rdap.org/domain/example.com", headers={"Accept": "application/rdap+json"})
            return CollectorHealth(
                self.name,
                "ONLINE" if r.status_code in (200, 404) else "DEGRADED",
                f"rdap.org HTTP {r.status_code}",
                int((time.perf_counter() - t) * 1000),
            )
        except Exception as exc:
            return CollectorHealth(self.name, "OFFLINE", f"rdap.org unreachable: {type(exc).__name__}")

    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
        from eyohe.core.urlnorm import host_of, registrable_domain

        res = CollectResult(collector=self.name)
        if target_type == TargetType.IP:
            url = f"https://rdap.org/ip/{value}"
            label = value
        else:
            host = (
                value.split("@")[-1]
                if target_type == TargetType.EMAIL
                else (host_of(value) if target_type == TargetType.URL else value)
            )
            label = registrable_domain(host) or host
            url = f"https://rdap.org/domain/{label}"
        async with SafeHttpClient(timeout=20) as c:
            r = await c.get(url, headers={"Accept": "application/rdap+json"})
        if r.status_code == 404:
            res.summary = {"note": f"no RDAP record for {label} (not registered or registry without RDAP)"}
            res.warnings.append(f"RDAP: no record found for {label}")
            return res
        if r.status_code == 429:
            raise CollectorError(self.name, "rdap.org rate limit reached", retry_after_seconds=60)
        if r.status_code >= 400:
            raise CollectorError(self.name, f"rdap.org returned HTTP {r.status_code}")
        import orjson

        try:
            data = orjson.loads(r.content)
        except orjson.JSONDecodeError as exc:
            raise CollectorError(self.name, "invalid RDAP JSON") from exc
        src = SourceItem(
            url=r.final_url or url,
            source_type=SourceType.TECHNICAL_RECORD,
            title=f"RDAP record for {label}",
            publisher=data.get("port43", "registry RDAP"),
            tier=3,
            reliability_note="Registry/registrar RDAP data; contact details are typically redacted for privacy.",
            text_content=r.text[:50000],
            content_type="application/rdap+json",
            http_status=r.status_code,
            raw_content=r.content,
            metadata={"handle": data.get("handle")},
        )
        res.sources.append(src)
        subject = EntityItem(EntityType.IP if target_type == TargetType.IP else EntityType.DOMAIN, label)
        key = "rdap-main"
        status = data.get("status", [])
        registrar = ""
        entities_out: list[EntityItem] = [subject]
        for ent in data.get("entities", []):
            roles = ent.get("roles", [])
            name = _vcard_name(ent)
            if "registrar" in roles and name:
                registrar = name
                org = EntityItem(EntityType.ORGANIZATION, name, attributes={"role": "registrar"})
                entities_out.append(org)
                res.relationships.append(
                    RelationshipItem(
                        subject,
                        org,
                        RelationshipType.REGISTERED_BY,
                        rationale="RDAP registrar entity",
                        evidence_keys=[key],
                    )
                )
            elif (
                ("registrant" in roles or "administrative" in roles)
                and name
                and "redacted" not in name.lower()
                and "privacy" not in name.lower()
            ):
                org = EntityItem(EntityType.ORGANIZATION, name, attributes={"role": ",".join(roles)})
                entities_out.append(org)
                res.relationships.append(
                    RelationshipItem(
                        org,
                        subject,
                        RelationshipType.OWNS,
                        rationale=f"RDAP {','.join(roles)} contact (public registry data)",
                        evidence_keys=[key],
                    )
                )
        nameservers = [
            ns.get("ldhName", "").lower().rstrip(".") for ns in data.get("nameservers", []) if ns.get("ldhName")
        ]
        for ns in nameservers:
            e = EntityItem(EntityType.NAMESERVER, ns)
            entities_out.append(e)
            res.relationships.append(
                RelationshipItem(
                    subject, e, RelationshipType.USES_NAMESERVER, rationale="RDAP nameserver", evidence_keys=[key]
                )
            )
        events = {}
        for ev in data.get("events", []):
            action, date = ev.get("eventAction", ""), ev.get("eventDate", "")
            if action and date:
                events[action] = date
        claim_parts = [f"RDAP record for {label}"]
        if registrar:
            claim_parts.append(f"registrar: {registrar}")
        if events.get("registration"):
            claim_parts.append(f"registered {events['registration'][:10]}")
        if events.get("expiration"):
            claim_parts.append(f"expires {events['expiration'][:10]}")
        if target_type == TargetType.IP:
            claim_parts.append(
                f"network: {data.get('name', '')} ({data.get('startAddress', '')}-{data.get('endAddress', '')}) country {data.get('country', '?')}"
            )
        if status:
            claim_parts.append(f"status: {', '.join(status)[:120]}")
        res.evidence.append(
            EvidenceItem(
                claim="; ".join(claim_parts)[:1000],
                evidence_type=EvidenceType.TECHNICAL_RECORD,
                excerpt=orjson.dumps(
                    {
                        "handle": data.get("handle"),
                        "status": status,
                        "events": events,
                        "nameservers": nameservers,
                        "registrar": registrar,
                        "name": data.get("name"),
                        "country": data.get("country"),
                    }
                ).decode()[:1500],
                source_url=src.url,
                structured={"events": events, "status": status, "nameservers": nameservers, "registrar": registrar},
                entities=entities_out,
                collection_method="rdap",
                key=key,
            )
        )
        for action, date in events.items():
            title = _EVENT_TITLES.get(action, f"RDAP event: {action}")
            if title is None:
                continue
            d = _dt(date)
            if d:
                res.timeline.append(
                    TimelineItem(
                        occurred_at=d,
                        title=f"{title} ({label})",
                        description=f"RDAP {action} event",
                        event_kind="REGISTRATION",
                        evidence_key=key,
                        entities=[subject],
                    )
                )
        res.summary = {"records": 1, "registrar": registrar, "nameservers": len(nameservers), "events": len(events)}
        await ctx.log(
            "RDAP",
            f"RDAP record collected for {label}" + (f" (registrar: {registrar})" if registrar else ""),
            **res.summary,
        )
        return res
