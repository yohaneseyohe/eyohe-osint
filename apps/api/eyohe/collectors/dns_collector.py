"""DNS enumeration via dnspython (public resolvers). Produces technical-record evidence per record
type, IP/nameserver/mail-server entities and RESOLVES_TO / USES_* relationships."""

from __future__ import annotations

import asyncio
import time

import dns.asyncresolver
import dns.exception
import dns.rdatatype
import dns.resolver

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

RECORD_TYPES = ("A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA", "CAA")


class DNSCollector(BaseCollector):
    name = "dns"
    description = "Public DNS records (A, AAAA, MX, NS, TXT, CNAME, SOA, CAA) with SPF/DMARC parsing"
    source_tier = 3
    supported_targets = frozenset({TargetType.DOMAIN, TargetType.EMAIL, TargetType.URL})
    stage = "DNS"

    def __init__(self) -> None:
        self.resolver = dns.asyncresolver.Resolver(configure=True)
        self.resolver.lifetime = 8.0
        self.resolver.timeout = 4.0

    async def health_check(self) -> CollectorHealth:
        t = time.perf_counter()
        try:
            await asyncio.wait_for(self.resolver.resolve("example.com", "A"), timeout=5)
            return CollectorHealth(self.name, "ONLINE", "resolver OK", int((time.perf_counter() - t) * 1000))
        except Exception as exc:
            return CollectorHealth(self.name, "OFFLINE", f"DNS resolution failed: {type(exc).__name__}")

    async def _query(self, name: str, rtype: str) -> list[str]:
        try:
            ans = await self.resolver.resolve(name, rtype)
            out = []
            for r in ans:
                if rtype == "TXT":
                    out.append(
                        "".join(s.decode("utf-8", "replace") if isinstance(s, bytes) else str(s) for s in r.strings)
                    )
                elif rtype == "MX":
                    out.append(f"{r.preference} {str(r.exchange).rstrip('.')}")
                elif rtype == "SOA":
                    out.append(
                        f"mname={str(r.mname).rstrip('.')} rname={str(r.rname).rstrip('.')} serial={r.serial} refresh={r.refresh} retry={r.retry} expire={r.expire} minimum={r.minimum}"
                    )
                elif rtype == "CAA":
                    out.append(
                        f"{r.flags} {r.tag.decode() if isinstance(r.tag, bytes) else r.tag} {r.value.decode() if isinstance(r.value, bytes) else r.value}"
                    )
                else:
                    out.append(str(r).rstrip("."))
            return out
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers):
            return []
        except dns.exception.Timeout:
            return ["__timeout__"]

    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
        from eyohe.core.urlnorm import host_of

        domain = (
            value.split("@")[-1]
            if target_type == TargetType.EMAIL
            else (host_of(value) if target_type == TargetType.URL else value)
        )
        domain = domain.lower().rstrip(".")
        res = CollectResult(collector=self.name)
        source_url = f"dns://{domain}"
        res.sources.append(
            SourceItem(
                url=source_url,
                source_type=SourceType.TECHNICAL_RECORD,
                title=f"DNS records for {domain}",
                publisher="public DNS",
                tier=3,
                reliability_note="Live DNS answer from the configured public resolver; authoritative data can change at any time.",
            )
        )
        domain_entity = EntityItem(EntityType.DOMAIN, domain)
        results = await asyncio.gather(*(self._query(domain, rt) for rt in RECORD_TYPES))
        records: dict[str, list[str]] = {}
        timeouts = []
        for rt, vals in zip(RECORD_TYPES, results, strict=True):
            if vals == ["__timeout__"]:
                timeouts.append(rt)
                continue
            if vals:
                records[rt] = sorted(vals)
        if timeouts:
            res.warnings.append(f"DNS timeout for record types: {', '.join(timeouts)}")
        if not records and len(timeouts) == len(RECORD_TYPES):
            raise CollectorError(
                self.name, "all DNS queries timed out", retry_after_seconds=30, impact="no DNS evidence"
            )
        # DMARC lives on a subdomain.
        dmarc = await self._query(f"_dmarc.{domain}", "TXT")
        if dmarc and dmarc != ["__timeout__"]:
            records["DMARC"] = dmarc
        text_blob = "\n".join(f"{rt}: {v}" for rt, vals in records.items() for v in vals)
        res.sources[0].text_content = text_blob
        res.sources[0].content_type = "text/plain"
        for rt, vals in records.items():
            key = f"dns-{rt}"
            ents: list[EntityItem] = [domain_entity]
            for v in vals:
                if not v.strip():
                    continue
                if rt in ("A", "AAAA"):
                    ents.append(EntityItem(EntityType.IP, v))
                elif rt == "NS":
                    ents.append(EntityItem(EntityType.NAMESERVER, v))
                elif rt == "MX":
                    exchange = v.split(" ", 1)[1].strip() if " " in v else ""
                    if exchange:  # "0 ." is a null MX: the domain explicitly accepts no mail
                        ents.append(EntityItem(EntityType.MAIL_SERVER, exchange))
                elif rt == "CNAME":
                    ents.append(EntityItem(EntityType.DOMAIN, v))
            claim = f"DNS {rt} record(s) for {domain}: {', '.join(vals)[:300]}"
            if rt == "MX" and all(not (v.split(" ", 1)[1].strip() if " " in v else "") for v in vals):
                claim = f"DNS MX for {domain} is a null MX record (the domain publishes that it accepts no email)"
            if rt == "TXT":
                spf = [v for v in vals if v.lower().startswith("v=spf1")]
                claim = (
                    f"DNS TXT records for {domain} ({len(vals)} records"
                    + (f"; SPF present: {spf[0][:120]}" if spf else "; no SPF")
                    + ")"
                )
                for v in vals:
                    for tok in v.split():
                        if tok.startswith("include:") and len(tok) > 8:
                            ents.append(EntityItem(EntityType.DOMAIN, tok.split(":", 1)[1].rstrip(".")))
            if rt == "DMARC":
                claim = f"DMARC policy published for {domain}: {vals[0][:160]}"
            res.evidence.append(
                EvidenceItem(
                    claim=claim,
                    evidence_type=EvidenceType.TECHNICAL_RECORD,
                    excerpt="\n".join(f"{rt}: {v}" for v in vals)[:1500],
                    source_url=source_url,
                    structured={"record_type": rt, "values": vals},
                    entities=ents,
                    collection_method="dns_query",
                    key=key,
                )
            )
            for e in ents[1:]:
                if e.type == EntityType.IP:
                    res.relationships.append(
                        RelationshipItem(
                            domain_entity,
                            e,
                            RelationshipType.RESOLVES_TO,
                            rationale=f"DNS {rt} record",
                            evidence_keys=[key],
                        )
                    )
                elif e.type == EntityType.NAMESERVER:
                    res.relationships.append(
                        RelationshipItem(
                            domain_entity,
                            e,
                            RelationshipType.USES_NAMESERVER,
                            rationale="DNS NS record",
                            evidence_keys=[key],
                        )
                    )
                elif e.type == EntityType.MAIL_SERVER:
                    res.relationships.append(
                        RelationshipItem(
                            domain_entity,
                            e,
                            RelationshipType.USES_MAIL_SERVER,
                            rationale="DNS MX record",
                            evidence_keys=[key],
                        )
                    )
                elif e.type == EntityType.DOMAIN and rt == "CNAME":
                    res.relationships.append(
                        RelationshipItem(
                            domain_entity,
                            e,
                            RelationshipType.RESOLVES_TO,
                            rationale="DNS CNAME record",
                            evidence_keys=[key],
                        )
                    )
        for ip in records.get("A", []) + records.get("AAAA", []):
            res.discovered_targets.append((TargetType.IP, ip))
        res.summary = {"records": sum(len(v) for v in records.values()), "record_types": sorted(records)}
        await ctx.log(
            "DNS",
            f"{res.summary['records']} DNS records collected ({', '.join(sorted(records)) or 'none'})",
            **res.summary,
        )
        return res
