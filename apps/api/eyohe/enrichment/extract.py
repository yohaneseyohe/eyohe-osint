"""Deterministic entity extraction from text (regex-based; no model needed).

The LLM may *propose* entities later, but every entity it proposes must also be found by this
extractor in the source text or it is rejected.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable

from eyohe.collectors.base import EntityItem
from eyohe.core.enums import EntityType

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}\b")
_URL = re.compile(r"\bhttps?://[^\s<>\"'()\[\]{}]+", re.I)
_DOMAIN = re.compile(r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:[a-z]{2,24})\b", re.I)
_IPV4 = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_IPV6 = re.compile(r"\b(?:[0-9a-f]{1,4}:){2,7}[0-9a-f]{1,4}\b", re.I)
_HANDLE = re.compile(r"(?<![\w.])@([A-Za-z0-9_]{3,30})\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?(?:\(?\d{2,4}\)?[\s.-]?)\d{3,4}[\s.-]?\d{3,4}(?!\w)")
_BTC = re.compile(r"\b(?:bc1[a-z0-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
_ETH = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
_GITHUB_REPO = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", re.I)
_SOCIAL = {
    "github": re.compile(r"github\.com/([A-Za-z0-9-]{1,39})(?:[/?#]|$)", re.I),
    "x": re.compile(r"(?:twitter|x)\.com/([A-Za-z0-9_]{1,15})(?:[/?#]|$)", re.I),
    "instagram": re.compile(r"instagram\.com/([A-Za-z0-9_.]{1,30})(?:[/?#]|$)", re.I),
    "linkedin": re.compile(r"linkedin\.com/(?:in|company)/([A-Za-z0-9_%-]{2,100})(?:[/?#]|$)", re.I),
    "reddit": re.compile(r"reddit\.com/(?:u|user)/([A-Za-z0-9_-]{3,20})(?:[/?#]|$)", re.I),
    "youtube": re.compile(r"youtube\.com/(?:@|c/|channel/|user/)([A-Za-z0-9_.-]{2,100})(?:[/?#]|$)", re.I),
    "tiktok": re.compile(r"tiktok\.com/@([A-Za-z0-9_.]{2,24})(?:[/?#]|$)", re.I),
    "telegram": re.compile(r"(?:t\.me|telegram\.me)/([A-Za-z0-9_]{5,32})(?:[/?#]|$)", re.I),
    "facebook": re.compile(r"facebook\.com/([A-Za-z0-9.]{5,50})(?:[/?#]|$)", re.I),
}
_SOCIAL_RESERVED = {
    "share",
    "intent",
    "home",
    "login",
    "search",
    "explore",
    "p",
    "reel",
    "hashtag",
    "settings",
    "about",
    "privacy",
    "help",
    "features",
    "pricing",
    "marketplace",
    "orgs",
    "topics",
    "sponsors",
    "pulls",
    "issues",
    "notifications",
    "watch",
    "channel",
    "results",
    "i",
    "status",
    "r",
    "wiki",
    "comments",
    "submit",
    "pages",
    "groups",
    "events",
    "jobs",
    "pub",
    "company",
    "school",
    "feed",
    "messaging",
    "mynetwork",
    "learning",
}
_FILE_EXT = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "svg",
    "css",
    "js",
    "json",
    "xml",
    "pdf",
    "zip",
    "tar",
    "gz",
    "mp4",
    "mp3",
    "woff",
    "woff2",
    "ttf",
    "ico",
    "webp",
    "txt",
    "md",
    "py",
    "ts",
    "tsx",
    "yml",
    "yaml",
    "html",
    "htm",
    "php",
    "asp",
    "aspx",
    "exe",
    "dll",
    "min",
    "map",
    "env",
    "lock",
    "toml",
    "ini",
    "log",
    "csv",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
}


def _is_public_ip(s: str) -> bool:
    try:
        ip = ipaddress.ip_address(s)
    except ValueError:
        return False
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    )


def _valid_domain(d: str) -> bool:
    import tldextract

    d = d.lower().strip(".")
    if d.rsplit(".", 1)[-1] in _FILE_EXT:
        return False
    ext = tldextract.extract(d)
    return bool(ext.suffix) and bool(ext.domain)


def extract_entities(
    text: str, *, max_per_type: int = 50, include_domains: bool = True, include_phones: bool = False
) -> list[EntityItem]:
    """Extract entities from free text. Phone extraction is opt-in because it is noisy."""
    found: dict[tuple[str, str], EntityItem] = {}

    def add(etype: EntityType, value: str, **attrs: str) -> None:
        key = (str(etype), value.lower())
        if key not in found and sum(1 for k in found if k[0] == str(etype)) < max_per_type:
            found[key] = EntityItem(etype, value, attributes=dict(attrs))

    for m in _EMAIL.finditer(text):
        add(EntityType.EMAIL, m.group(0).lower())
    for m in _URL.finditer(text):
        url = m.group(0).rstrip(".,;:!?)")
        for platform, pat in _SOCIAL.items():
            sm = pat.search(url)
            if sm and sm.group(1).lower() not in _SOCIAL_RESERVED:
                handle = sm.group(1)
                if platform == "github":
                    rm = _GITHUB_REPO.search(url)
                    if rm and rm.group(2).lower() not in _SOCIAL_RESERVED:
                        add(EntityType.REPOSITORY, f"{rm.group(1)}/{rm.group(2)}", platform="github", url=url)
                add(
                    EntityType.SOCIAL_ACCOUNT, f"{platform}:{handle.lower()}", platform=platform, handle=handle, url=url
                )
                break
        else:
            add(EntityType.URL, url)
    if include_domains:
        for m in _DOMAIN.finditer(text):
            d = m.group(0).lower()
            if _valid_domain(d) and not _IPV4.fullmatch(d):
                add(EntityType.DOMAIN, d)
    for m in _IPV4.finditer(text):
        if _is_public_ip(m.group(0)):
            add(EntityType.IP, m.group(0))
    for m in _IPV6.finditer(text):
        if "::" in m.group(0) or m.group(0).count(":") >= 4:
            if _is_public_ip(m.group(0)):
                add(EntityType.IP, m.group(0).lower())
    for m in _HANDLE.finditer(text):
        add(EntityType.USERNAME, m.group(1))
    if include_phones:
        for m in _PHONE.finditer(text):
            digits = re.sub(r"\D", "", m.group(0))
            if 8 <= len(digits) <= 15:
                add(EntityType.PHONE, m.group(0).strip())
    for m in _BTC.finditer(text):
        add(EntityType.CRYPTO_ADDRESS, m.group(0), chain="bitcoin")
    for m in _ETH.finditer(text):
        add(EntityType.CRYPTO_ADDRESS, m.group(0), chain="ethereum")
    return list(found.values())


def entity_values(items: Iterable[EntityItem], etype: EntityType) -> list[str]:
    return [i.value for i in items if i.type == etype]
