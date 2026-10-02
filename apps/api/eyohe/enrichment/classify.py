"""Target classification and value normalization (deterministic, no LLM needed)."""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlsplit

from eyohe.core.enums import TargetType
from eyohe.core.urlnorm import normalize_url

_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_DOMAIN = re.compile(r"^(?=.{1,253}$)(?!-)([A-Za-z0-9-]{1,63}(?<!-)\.)+[A-Za-z]{2,63}$")
_USERNAME = re.compile(r"^@?[A-Za-z0-9_.-]{2,64}$")
_PHONE = re.compile(r"^\+?[0-9][0-9 ()\-.]{6,20}$")
_BTC = re.compile(r"^(bc1[a-z0-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})$")
_ETH = re.compile(r"^0x[a-fA-F0-9]{40}$")
_SOCIAL_HOSTS = {
    "instagram.com": "instagram",
    "www.instagram.com": "instagram",
    "twitter.com": "x",
    "x.com": "x",
    "www.x.com": "x",
    "reddit.com": "reddit",
    "www.reddit.com": "reddit",
    "old.reddit.com": "reddit",
    "github.com": "github",
    "www.github.com": "github",
    "linkedin.com": "linkedin",
    "www.linkedin.com": "linkedin",
    "tiktok.com": "tiktok",
    "www.tiktok.com": "tiktok",
    "youtube.com": "youtube",
    "www.youtube.com": "youtube",
    "facebook.com": "facebook",
    "www.facebook.com": "facebook",
    "t.me": "telegram",
    "telegram.me": "telegram",
}


def classify_target(raw: str) -> tuple[TargetType, str, dict[str, str]]:
    """Return (type, normalized_value, extra)."""
    value = raw.strip()
    extra: dict[str, str] = {}
    if not value:
        return TargetType.UNKNOWN, value, extra
    # Explicit prefixes: "username:foo", "org:Acme"
    m = re.match(
        r"^(domain|ip|email|username|user|org|organization|company|person|url|phone|crypto|social):\s*(.+)$",
        value,
        re.I,
    )
    if m:
        kind, v = m.group(1).lower(), m.group(2).strip()
        mapping = {
            "domain": TargetType.DOMAIN,
            "ip": TargetType.IP,
            "email": TargetType.EMAIL,
            "username": TargetType.USERNAME,
            "user": TargetType.USERNAME,
            "org": TargetType.ORGANIZATION,
            "organization": TargetType.ORGANIZATION,
            "company": TargetType.COMPANY,
            "person": TargetType.PERSON,
            "url": TargetType.URL,
            "phone": TargetType.PHONE,
            "crypto": TargetType.CRYPTO_ADDRESS,
            "social": TargetType.SOCIAL_ACCOUNT,
        }
        t = mapping[kind]
        norm = _normalize_for(t, v)
        return t, norm, extra
    try:
        ipaddress.ip_address(value)
        return TargetType.IP, value, extra
    except ValueError:
        pass
    if _EMAIL.match(value):
        return TargetType.EMAIL, value.lower(), extra
    if "://" in value or value.startswith("www."):
        url = value if "://" in value else "https://" + value
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        platform = _SOCIAL_HOSTS.get(host)
        path = parts.path.strip("/")
        if platform and path and "/" not in path.strip("@") and path not in ("r", "u", "in"):
            handle = path.lstrip("@")
            extra["platform"] = platform
            return TargetType.SOCIAL_ACCOUNT, f"{platform}:{handle.lower()}", extra
        if platform == "reddit" and path.startswith(("u/", "user/")):
            extra["platform"] = "reddit"
            return TargetType.SOCIAL_ACCOUNT, "reddit:" + path.split("/", 1)[1].split("/")[0].lower(), extra
        if platform == "linkedin" and path.startswith("in/"):
            extra["platform"] = "linkedin"
            return TargetType.SOCIAL_ACCOUNT, "linkedin:" + path.split("/", 1)[1].split("/")[0].lower(), extra
        if platform == "github" and path and "/" in path:
            extra["platform"] = "github"
            return TargetType.URL, normalize_url(url), extra
        if path == "" and host:
            return TargetType.DOMAIN, host, extra
        return TargetType.URL, normalize_url(url), extra
    if _DOMAIN.match(value):
        return TargetType.DOMAIN, value.lower().rstrip("."), extra
    if _BTC.match(value) or _ETH.match(value):
        extra["chain"] = "ethereum" if _ETH.match(value) else "bitcoin"
        return TargetType.CRYPTO_ADDRESS, value, extra
    if _PHONE.match(value) and sum(c.isdigit() for c in value) >= 7:
        return TargetType.PHONE, re.sub(r"[^0-9+]", "", value), extra
    if value.startswith("@") and _USERNAME.match(value):
        return TargetType.USERNAME, value.lstrip("@").lower(), extra
    words = value.split()
    if len(words) == 1 and _USERNAME.match(value) and not value.isalpha():
        return TargetType.USERNAME, value.lower(), extra
    if len(words) == 1 and _USERNAME.match(value):
        # A single alphabetic token is ambiguous: treat as username, planner also tries org search.
        return TargetType.USERNAME, value.lower(), extra
    org_hints = (
        "inc",
        "llc",
        "ltd",
        "corp",
        "gmbh",
        "technologies",
        "labs",
        "group",
        "company",
        "co.",
        "plc",
        "s.a.",
        "ag",
        "foundation",
        "university",
    )
    if any(w.lower().strip(".,") in org_hints for w in words):
        return TargetType.ORGANIZATION, value, extra
    if 2 <= len(words) <= 4 and all(w[:1].isupper() for w in words if w.isalpha()):
        return TargetType.PERSON, value, extra
    return TargetType.ORGANIZATION, value, extra


def _normalize_for(t: TargetType, v: str) -> str:
    if t in (TargetType.DOMAIN, TargetType.EMAIL, TargetType.USERNAME):
        return v.lower().lstrip("@").rstrip(".")
    if t == TargetType.URL:
        return normalize_url(v)
    if t == TargetType.PHONE:
        return re.sub(r"[^0-9+]", "", v)
    return v
