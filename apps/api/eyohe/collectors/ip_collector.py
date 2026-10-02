"""IP enrichment from public DNS-based registries: reverse DNS (PTR) and Team Cymru's ASN
lookup service (origin.asn.cymru.com TXT) — no API keys, no scanning."""

from __future__ import annotations

import ipaddress
import time

import dns.asyncresolver
import dns.resolver
import dns.reversename

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


class IPInfoCollector(BaseCollector):
    name = "ip_info"
    description = "Reverse DNS and ASN/network ownership (Team Cymru DNS service)"
    source_tier = 3
    supported_targets = frozenset({TargetType.IP})
    stage = "IP"

    def __init__(self) -> None:
        self.resolver = dns.asyncresolver.Resolver(configure=True)
        self.resolver.lifetime = 8.0

    async def health_check(self) -> CollectorHealth:
        t = time.perf_counter()
        try:
            await self.resolver.resolve("8.8.8.8.origin.asn.cymru.com", "TXT")
            return CollectorHealth(self.name, "ONLINE", "cymru ASN service OK", int((time.perf_counter() - t) * 1000))
        except Exception as exc:
            return CollectorHealth(self.name, "OFFLINE", f"ASN lookup failed: {type(exc).__name__}")

    async def _txt(self, name: str) -> list[str]:
        try:
            ans = await self.resolver.resolve(name, "TXT")
            return ["".join(s.decode() if isinstance(s, bytes) else s for s in r.strings) for r in ans]
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN, dns.resolver.NoNameservers, dns.exception.Timeout):
            return []

    async def collect(self, ctx: CollectContext, target_type: TargetType, value: str) -> CollectResult:
        res = CollectResult(collector=self.name)
        ip = ipaddress.ip_address(value)
        ip_entity = EntityItem(EntityType.IP, str(ip))
        src_url = f"dns://cymru/{ip}"
        res.sources.append(
            SourceItem(
                url=src_url,
                source_type=SourceType.TECHNICAL_RECORD,
                title=f"IP enrichment for {ip}",
                publisher="Team Cymru / reverse DNS",
                tier=3,
                reliability_note="Routing-table derived ASN data and PTR record; indicates network ownership, not the operator of a service.",
            )
        )
        ptr = ""
        try:
            ans = await self.resolver.resolve(dns.reversename.from_address(str(ip)), "PTR")
            ptr = str(ans[0]).rstrip(".")
        except Exception:
            ptr = ""
        if ip.version == 4:
            rev = ".".join(reversed(str(ip).split(".")))
            q = f"{rev}.origin.asn.cymru.com"
        else:
            nibbles = ip.exploded.replace(":", "")
            q = ".".join(reversed(nibbles)) + ".origin6.asn.cymru.com"
        origin = await self._txt(q)
        asn = prefix = cc = registry = allocated = asname = ""
        if origin:
            parts = [p.strip() for p in origin[0].split("|")]
            if len(parts) >= 5:
                asn, prefix, cc, registry, allocated = parts[0].split()[0], parts[1], parts[2], parts[3], parts[4]
            asinfo = await self._txt(f"AS{asn}.asn.cymru.com") if asn else []
            if asinfo:
                asname = asinfo[0].split("|")[-1].strip()
        ents = [ip_entity]
        if ptr:
            ents.append(EntityItem(EntityType.DOMAIN, ptr))
        if asn:
            asn_entity = EntityItem(
                EntityType.ASN,
                f"AS{asn}",
                label=asname or f"AS{asn}",
                attributes={"name": asname, "country": cc, "registry": registry, "prefix": prefix},
            )
            ents.append(asn_entity)
            res.relationships.append(
                RelationshipItem(
                    ip_entity,
                    asn_entity,
                    RelationshipType.HOSTED_ON,
                    rationale="BGP origin ASN (Team Cymru)",
                    evidence_keys=["ip-asn"],
                )
            )
        claim = (
            f"IP {ip}: "
            + (f"PTR {ptr}; " if ptr else "no PTR record; ")
            + (
                f"announced by AS{asn} ({asname}) prefix {prefix}, registry {registry.upper()}, country {cc}, allocated {allocated}"
                if asn
                else "no BGP origin found"
            )
        )
        res.sources[0].text_content = claim
        res.evidence.append(
            EvidenceItem(
                claim=claim[:1000],
                evidence_type=EvidenceType.TECHNICAL_RECORD,
                excerpt="\n".join(origin)[:500],
                source_url=src_url,
                structured={
                    "ptr": ptr,
                    "asn": asn,
                    "as_name": asname,
                    "prefix": prefix,
                    "country": cc,
                    "registry": registry,
                    "allocated": allocated,
                },
                entities=ents,
                collection_method="dns_ptr+cymru",
                key="ip-asn",
            )
        )
        if ptr:
            res.relationships.append(
                RelationshipItem(
                    EntityItem(EntityType.DOMAIN, ptr),
                    ip_entity,
                    RelationshipType.RESOLVES_TO,
                    rationale="reverse DNS (PTR)",
                    evidence_keys=["ip-asn"],
                )
            )
        res.summary = {"records": 1, "asn": asn, "ptr": ptr}
        await ctx.log("IP", claim[:200], **res.summary)
        return res
