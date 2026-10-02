"""Universal search: map natural-language analyst requests to structured queries.

Rule-based first (fast, deterministic, works offline); the AI analyst handles anything else."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Intent:
    kind: str  # evidence | sources | entities | findings | contradictions | relationships | report | timeline | ask
    filters: dict[str, Any] = field(default_factory=dict)
    route: str = ""
    explanation: str = ""
    year: int | None = None


_SOURCE_HINTS = {
    "github": "github",
    "reddit": "reddit",
    "news": "news",
    "dns": "dns",
    "rdap": "rdap",
    "whois": "rdap",
    "archive": "wayback",
    "wayback": "wayback",
    "certificate": "ct_logs",
    "social": "social_profiles",
}
_ENTITY_TYPES = {
    "domain": "DOMAIN",
    "domains": "DOMAIN",
    "ip": "IP",
    "ips": "IP",
    "email": "EMAIL",
    "emails": "EMAIL",
    "username": "USERNAME",
    "usernames": "USERNAME",
    "person": "PERSON",
    "people": "PERSON",
    "organization": "ORGANIZATION",
    "organisations": "ORGANIZATION",
    "organizations": "ORGANIZATION",
    "company": "COMPANY",
    "companies": "COMPANY",
    "repository": "REPOSITORY",
    "repositories": "REPOSITORY",
    "repos": "REPOSITORY",
    "account": "SOCIAL_ACCOUNT",
    "accounts": "SOCIAL_ACCOUNT",
    "subdomain": "DOMAIN",
    "subdomains": "DOMAIN",
}


def parse_intent(text: str, case_id: str | None = None) -> Intent:
    q = text.strip()
    low = q.lower()
    year_m = re.search(r"\b(20[0-3]\d|19\d\d)\b", low)
    year = int(year_m.group(1)) if year_m else None
    base = f"/cases/{case_id}" if case_id else ""
    if re.search(r"\b(generate|create|build|make|export)\b.*\breport\b", low) or low.startswith("report"):
        return Intent(
            "report",
            {"format": "pdf" if "pdf" in low else ("docx" if "docx" in low or "word" in low else "html")},
            f"{base}?tab=reports",
            "Generate an investigation report.",
            year,
        )
    if "contradict" in low or "conflict" in low or "disagree" in low:
        return Intent(
            "contradictions",
            {"confidence": "CONTRADICTED"},
            f"{base}?tab=evidence&confidence=CONTRADICTED",
            "Show evidence and findings marked CONTRADICTED.",
            year,
        )
    if "timeline" in low or "chronolog" in low or re.search(r"\bwhen\b", low):
        return Intent("timeline", {"year": year} if year else {}, f"{base}?tab=timeline", "Open the timeline.", year)
    m = re.search(r"evidence\s+(?:supporting|for|about|on|related to)\s+(.+)$", low)
    if m:
        term = m.group(1).strip(" ?.")
        return Intent(
            "evidence",
            {"q": term, **({"year": year} if year else {})},
            f"{base}?tab=evidence&q={term}",
            f"Search evidence for '{term}'.",
            year,
        )
    if re.search(r"\b(relationship|relationships|connected|linked|graph|association)\b", low):
        return Intent("relationships", {}, f"{base}?tab=graph", "Open the graph and relationship list.", year)
    if re.search(r"\b(which|what)\s+sources?\b", low) or low.startswith("sources"):
        m = re.search(r"mention(?:s|ing)?\s+(.+)$", low)
        return Intent(
            "sources",
            {"q": m.group(1).strip(" ?.") if m else ""},
            f"{base}?tab=sources",
            "List sources" + (f" mentioning '{m.group(1).strip(' ?.')}'" if m else ""),
            year,
        )
    for word, collector in _SOURCE_HINTS.items():
        if re.search(rf"\b{word}\b", low) and re.search(
            r"\b(reference|references|mention|mentions|result|results|show|list|find|all)\b", low
        ):
            kind = "evidence"
            return Intent(
                kind,
                {"collector": collector} if collector not in ("github", "reddit", "news") else {"q": word},
                f"{base}?tab=evidence&collector={collector}",
                f"Show evidence collected by the {word} collector.",
                year,
            )
    for word, etype in _ENTITY_TYPES.items():
        if re.search(rf"\b{word}\b", low) and re.search(r"\b(show|list|all|find|which|what)\b", low):
            return Intent(
                "entities", {"type": etype}, f"{base}?tab=entities&type={etype}", f"List {etype} entities.", year
            )
    m = re.search(r"evidence\s+(?:supporting|for|about|on|related to)\s+(.+)$", low)
    if m or "evidence" in low:
        term = m.group(1).strip(" ?.") if m else re.sub(r"\b(show|find|all|evidence|the|me)\b", "", low).strip()
        return Intent(
            "evidence",
            {"q": term, **({"year": year} if year else {})},
            f"{base}?tab=evidence&q={term}",
            f"Search evidence for '{term}'.",
            year,
        )
    if year and re.search(r"\b(reference|references|from|in|during)\b", low):
        return Intent(
            "evidence", {"year": year}, f"{base}?tab=evidence&year={year}", f"Show evidence observed in {year}.", year
        )
    if re.search(r"\b(finding|findings)\b", low):
        return Intent("findings", {}, f"{base}?tab=findings", "List findings.", year)
    return Intent(
        "ask", {"question": q}, f"{base}?tab=analyst&q={q}", "Ask the AI analyst (answers cite case evidence).", year
    )
