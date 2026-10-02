"""Evidence-based confidence engine.

Confidence is *computed* from evidence attached to a finding/relationship, never asserted by the
LLM. The rationale is returned so the UI can answer "Why?".

Rules (in order):
- Any contradicting evidence from a source of tier <= the best supporting tier  -> CONTRADICTED
- Analyst ACCEPTED review of a tier-1/2 backed claim                             -> CONFIRMED
- Analyst REJECTED                                                                -> CONTRADICTED
- >= 2 independent domains with at least one tier <= 3 and no contradiction       -> CORROBORATED
- 1 source of tier <= 2 (official/reputable) or 2 sources of any tier            -> SUPPORTED
- 1 source tier 3-4                                                               -> POSSIBLE
- only SYSTEM_INTERPRETATION evidence                                             -> INFERENCE
- nothing                                                                         -> UNVERIFIED
Identity claims (same-person) never exceed POSSIBLE without analyst acceptance.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from eyohe.core.enums import Confidence, EvidenceType, ReviewState
from eyohe.core.urlnorm import registrable_domain
from eyohe.models.evidence import Evidence


@dataclass
class ConfidenceResult:
    label: str
    reasons: list[str] = field(default_factory=list)
    supporting: list[str] = field(default_factory=list)
    contradicting: list[str] = field(default_factory=list)
    independent_sources: int = 0
    best_tier: int | None = None
    source_quality: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "reasons": self.reasons,
            "supporting": self.supporting,
            "contradicting": self.contradicting,
            "independent_sources": self.independent_sources,
            "best_tier": self.best_tier,
            "source_quality": self.source_quality,
        }


TIER_LABEL = {
    1: "official primary source",
    2: "reputable secondary source",
    3: "public technical database",
    4: "community discussion",
    5: "unverified source",
}


def _domain_of(e: Evidence, source_domains: dict[uuid.UUID, str]) -> str:
    if e.source_id and e.source_id in source_domains:
        return source_domains[e.source_id]
    url = (e.structured or {}).get("url") or (e.structured or {}).get("source_url")
    return registrable_domain(url) if url else f"collector:{e.collector}"


def assess(
    evidence: list[Evidence],
    roles: dict[uuid.UUID, str] | None = None,
    *,
    identity_claim: bool = False,
    review_state: str | None = None,
    source_tiers: dict[uuid.UUID, int] | None = None,
    source_domains: dict[uuid.UUID, str] | None = None,
) -> ConfidenceResult:
    roles = roles or {}
    source_tiers = source_tiers or {}
    source_domains = source_domains or {}
    supporting = [
        e for e in evidence if roles.get(e.id, "supports") == "supports" and e.review_state != ReviewState.REJECTED
    ]
    contradicting = [e for e in evidence if roles.get(e.id) == "contradicts" and e.review_state != ReviewState.REJECTED]

    def tier(e: Evidence) -> int:
        if e.source_id and e.source_id in source_tiers:
            return source_tiers[e.source_id]
        return int((e.structured or {}).get("tier", 5) or 5)

    res = ConfidenceResult(label=Confidence.UNVERIFIED)
    res.supporting = [e.display_id for e in supporting]
    res.contradicting = [e.display_id for e in contradicting]

    if review_state == ReviewState.REJECTED:
        res.label = Confidence.CONTRADICTED
        res.reasons.append("Analyst rejected this claim after review.")
        return res

    if not supporting and not contradicting:
        res.reasons.append("No evidence is attached.")
        return res

    best_sup = min((tier(e) for e in supporting), default=None)
    best_con = min((tier(e) for e in contradicting), default=None)
    res.best_tier = best_sup
    if best_sup is not None:
        res.source_quality = TIER_LABEL.get(best_sup, "")

    if contradicting and (best_sup is None or (best_con is not None and best_con <= best_sup)):
        res.label = Confidence.CONTRADICTED
        res.reasons.append(
            f"{len(contradicting)} contradicting evidence record(s) from source quality "
            f"'{TIER_LABEL.get(best_con or 5)}' outweigh or match the supporting evidence."
        )
        return res

    domains = {_domain_of(e, source_domains) for e in supporting}
    res.independent_sources = len(domains)
    non_inference = [e for e in supporting if e.evidence_type != EvidenceType.SYSTEM_INTERPRETATION]

    if not non_inference:
        res.label = Confidence.INFERENCE
        res.reasons.append("Only system interpretation supports this claim; no direct source evidence.")
        return res

    if review_state == ReviewState.ACCEPTED and best_sup is not None and best_sup <= 2:
        res.label = Confidence.CONFIRMED
        res.reasons.append("Analyst accepted the claim and it is backed by an official or reputable source.")
    elif len(domains) >= 2 and best_sup is not None and best_sup <= 3:
        res.label = Confidence.CORROBORATED
        res.reasons.append(f"{len(domains)} independent sources agree; best source quality: {TIER_LABEL[best_sup]}.")
    elif (best_sup is not None and best_sup <= 2) or len(non_inference) >= 2:
        res.label = Confidence.SUPPORTED
        res.reasons.append(
            "Backed by an official/reputable source."
            if best_sup is not None and best_sup <= 2
            else f"{len(non_inference)} evidence records from {len(domains)} source(s) support the claim."
        )
    else:
        res.label = Confidence.POSSIBLE
        res.reasons.append(f"Single source of quality '{TIER_LABEL.get(best_sup or 5)}'; requires corroboration.")

    if contradicting:
        res.reasons.append(f"{len(contradicting)} lower-quality contradicting record(s) exist; review recommended.")

    if (
        identity_claim
        and review_state != ReviewState.ACCEPTED
        and res.label in (Confidence.CONFIRMED, Confidence.CORROBORATED, Confidence.SUPPORTED)
    ):
        res.label = Confidence.POSSIBLE
        res.reasons.append(
            "Identity claims (same person/entity) are capped at POSSIBLE until an analyst confirms them."
        )
    if review_state == ReviewState.NEEDS_VERIFICATION and res.label in (Confidence.CONFIRMED, Confidence.CORROBORATED):
        res.label = Confidence.SUPPORTED
        res.reasons.append("Analyst flagged this for verification.")
    return res
