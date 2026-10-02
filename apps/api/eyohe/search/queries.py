"""Search query intelligence: branch generation and dork policy.

Operators like site:, intitle:, inurl:, filetype: and quoted phrases are supported. Queries that
look like credential hunting (e.g. ``filetype:env``, ``intext:password``) are refused because
they target private material rather than public information about the target.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from eyohe.core.enums import TargetType

_BLOCKED = [
    re.compile(r"filetype:(env|pem|key|ppk|sql|bak|log|htpasswd|kdbx|ovpn)\b", re.I),
    re.compile(
        r"\b(intext|inurl|intitle):\s*\"?(password|passwd|pwd|secret|api[_-]?key|private[_-]?key|token)\b", re.I
    ),
    re.compile(r"\b(password|passwd|credentials?|secret_key|aws_secret)\b.*\b(filetype|ext):", re.I),
    re.compile(r"\"?(BEGIN RSA PRIVATE KEY|BEGIN OPENSSH PRIVATE KEY)\"?", re.I),
    re.compile(r"\bindex of\b.*\b(backup|\.git|wp-config|\.ssh)\b", re.I),
]


@dataclass
class QueryBranch:
    name: str
    query: str
    category: str = "general"  # general | news | code | social | documents


def is_query_allowed(query: str) -> tuple[bool, str]:
    for pat in _BLOCKED:
        if pat.search(query):
            return False, "Query refused: it targets credentials/private material rather than public information."
    if len(query) > 400:
        return False, "Query too long."
    return True, ""


def quoted(value: str) -> str:
    return f'"{value}"' if " " in value or "." in value else value


def generate_branches(ttype: TargetType, value: str, *, objective: str = "") -> list[QueryBranch]:
    q = quoted(value)
    out: list[QueryBranch] = []
    if ttype == TargetType.DOMAIN:
        out += [
            QueryBranch("Site pages", f"site:{value}", "general"),
            QueryBranch("External references", f'"{value}" -site:{value}', "general"),
            QueryBranch("Code references", f'"{value}" site:github.com', "code"),
            QueryBranch("Community discussion", f'"{value}" site:reddit.com', "social"),
            QueryBranch("Professional references", f'"{value}" site:linkedin.com', "social"),
            QueryBranch("Documents", f'"{value}" filetype:pdf', "documents"),
            QueryBranch("News", f'"{value}"', "news"),
        ]
    elif ttype in (TargetType.ORGANIZATION, TargetType.COMPANY):
        out += [
            QueryBranch("Official", f"{q} official website", "general"),
            QueryBranch("Code", f"{q} site:github.com", "code"),
            QueryBranch("Community", f"{q} site:reddit.com", "social"),
            QueryBranch("Professional", f"{q} site:linkedin.com", "social"),
            QueryBranch("Documents", f"{q} filetype:pdf", "documents"),
            QueryBranch("Press", f"{q} press release OR announcement", "news"),
            QueryBranch("News", q, "news"),
        ]
    elif ttype in (TargetType.USERNAME, TargetType.SOCIAL_ACCOUNT):
        h = value.split(":", 1)[-1]
        out += [
            QueryBranch("Exact handle", f'"{h}"', "general"),
            QueryBranch("Mentions", f'"@{h}"', "social"),
            QueryBranch("Code", f'"{h}" site:github.com', "code"),
            QueryBranch("Reddit", f'"{h}" site:reddit.com', "social"),
            QueryBranch("X", f'"{h}" (site:twitter.com OR site:x.com)', "social"),
            QueryBranch("Instagram", f'"{h}" site:instagram.com', "social"),
            QueryBranch("YouTube", f'"{h}" site:youtube.com', "social"),
        ]
    elif ttype == TargetType.EMAIL:
        local, _, dom = value.partition("@")
        out += [
            QueryBranch("Exact", f'"{value}"', "general"),
            QueryBranch("Code", f'"{value}" site:github.com', "code"),
            QueryBranch("Local part + domain", f'"{local}" "{dom}"', "general"),
        ]
    elif ttype == TargetType.PERSON:
        out += [
            QueryBranch("Name", q, "general"),
            QueryBranch("Professional", f"{q} site:linkedin.com", "social"),
            QueryBranch("Code", f"{q} site:github.com", "code"),
            QueryBranch("Talks & publications", f"{q} (interview OR talk OR paper OR conference)", "general"),
            QueryBranch("News", q, "news"),
        ]
    elif ttype == TargetType.IP:
        out += [
            QueryBranch("Exact", f'"{value}"', "general"),
            QueryBranch("Abuse reports", f'"{value}" (abuse OR blocklist OR spam)', "general"),
            QueryBranch("Code", f'"{value}" site:github.com', "code"),
        ]
    elif ttype == TargetType.URL:
        out += [QueryBranch("Links to URL", f'"{value}"', "general")]
    elif ttype == TargetType.CRYPTO_ADDRESS:
        out += [
            QueryBranch("Exact", f'"{value}"', "general"),
            QueryBranch("Code", f'"{value}" site:github.com', "code"),
            QueryBranch("Forums", f'"{value}" site:reddit.com', "social"),
        ]
    else:
        out += [QueryBranch("General", q, "general")]
    # Objective keywords add one focused branch (e.g. "employees", "infrastructure")
    kw = _objective_keywords(objective)
    if kw:
        out.append(QueryBranch("Objective focus", f"{q} {' '.join(kw[:3])}", "general"))
    return [b for b in out if is_query_allowed(b.query)[0]]


_STOP = {
    "investigate",
    "identify",
    "the",
    "and",
    "its",
    "this",
    "that",
    "using",
    "only",
    "public",
    "publicly",
    "available",
    "information",
    "research",
    "find",
    "with",
    "for",
    "from",
    "about",
    "into",
    "all",
    "any",
    "relevant",
    "associated",
    "related",
    "references",
    "sources",
}


def _objective_keywords(objective: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z-]{3,}", objective.lower())
    seen: list[str] = []
    for w in words:
        if w not in _STOP and w not in seen:
            seen.append(w)
    return seen[:5]
