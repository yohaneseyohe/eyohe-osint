"""Investigation planning.

Plans are built from deterministic per-target-type templates so the system is predictable and
works offline. Phase 5 adds an Ollama step that may *adapt* the template (reorder, drop, add
search branches, write rationale) but can only use registered task types.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from eyohe.core.enums import TargetType


@dataclass
class PlannedTask:
    task_type: str  # registered tool/collector name
    title: str
    rationale: str
    category: str  # search | technical | social | historical | verification | reporting
    params: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    optional: bool = False


@dataclass
class Plan:
    objective: str
    target_type: str
    target_value: str
    tasks: list[PlannedTask]
    branches: list[str] = field(default_factory=list)  # human-readable search branches
    source: str = "template"  # template | ollama
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# Task catalogue: the only task types the planner (or the LLM) may emit.
TASK_CATALOGUE: dict[str, dict[str, str]] = {
    "dns": {"title": "DNS enumeration", "category": "technical", "stage": "DNS"},
    "rdap": {"title": "RDAP / WHOIS registration data", "category": "technical", "stage": "RDAP"},
    "ct_logs": {"title": "Certificate transparency", "category": "technical", "stage": "CT"},
    "subdomains": {"title": "Public subdomain discovery", "category": "technical", "stage": "CT"},
    "web_fetch": {"title": "Public website fingerprint", "category": "technical", "stage": "WEB"},
    "ip_info": {"title": "IP / ASN enrichment", "category": "technical", "stage": "IP"},
    "search_web": {"title": "Search-engine research", "category": "search", "stage": "SEARCH"},
    "search_news": {"title": "News research", "category": "search", "stage": "NEWS"},
    "github": {"title": "GitHub references", "category": "social", "stage": "GITHUB"},
    "reddit": {"title": "Reddit references", "category": "social", "stage": "REDDIT"},
    "social_profiles": {"title": "Public social profile lookup", "category": "social", "stage": "SOCIAL"},
    "wayback": {"title": "Historical archive research", "category": "historical", "stage": "ARCHIVE"},
    "documents": {"title": "Public document discovery", "category": "search", "stage": "DOCS"},
    "research_agent": {"title": "AI internet research loop", "category": "search", "stage": "AI"},
    "correlate": {"title": "Entity correlation", "category": "verification", "stage": "GRAPH"},
    "verify": {"title": "Cross-source verification", "category": "verification", "stage": "VERIFY"},
    "summarize": {"title": "Evidence summary & findings", "category": "verification", "stage": "AI"},
}


def _t(
    task_type: str,
    rationale: str,
    *,
    category: str | None = None,
    params: dict[str, Any] | None = None,
    optional: bool = False,
) -> PlannedTask:
    meta = TASK_CATALOGUE[task_type]
    return PlannedTask(task_type, meta["title"], rationale, category or meta["category"], params or {}, True, optional)


def _common_tail(value: str) -> list[PlannedTask]:
    return [
        _t(
            "correlate",
            "Link entities discovered by different collectors so relationships can be inspected in the graph.",
        ),
        _t("verify", "Compare independent sources, compute evidence-based confidence and flag contradictions."),
        _t(
            "summarize",
            "Draft findings strictly from collected evidence (every claim cites evidence IDs).",
            optional=True,
        ),
    ]


def _search_branches(value: str, ttype: TargetType) -> list[str]:
    q = f'"{value}"' if " " in value else value
    base = [q, f"{q} site:github.com", f"{q} site:reddit.com", f"{q} site:linkedin.com", f"{q} filetype:pdf"]
    if ttype == TargetType.DOMAIN:
        base = [
            f"site:{value}",
            f'"{value}" -site:{value}',
            f'"{value}" site:github.com',
            f'"{value}" site:reddit.com',
            f'"{value}" news',
            f"{value} filetype:pdf",
        ]
    elif ttype in (TargetType.ORGANIZATION, TargetType.COMPANY):
        base += [f"{q} official website", f"{q} news", f"{q} employees", f"{q} domains"]
    elif ttype == TargetType.USERNAME:
        base = [
            f'"{value}"',
            f'"{value}" site:github.com',
            f'"{value}" site:reddit.com',
            f'"{value}" site:twitter.com OR site:x.com',
            f'"{value}" site:instagram.com',
            f'"@{value}"',
        ]
    elif ttype == TargetType.EMAIL:
        base = [
            f'"{value}"',
            f'"{value}" site:github.com',
            f'"{value}" site:pastebin.com',
            f'"{value.split("@")[0]}" "{value.split("@")[1]}"',
        ]
    elif ttype == TargetType.PERSON:
        base = [q, f"{q} linkedin", f"{q} github", f"{q} news", f"{q} interview OR talk OR presentation"]
    elif ttype == TargetType.IP:
        base = [f'"{value}"', f'"{value}" abuse OR blocklist', f'"{value}" site:github.com']
    return base


def build_template_plan(objective: str, ttype: TargetType, value: str) -> Plan:
    tasks: list[PlannedTask] = []
    if ttype == TargetType.DOMAIN:
        tasks += [
            _t("dns", "Resolve A/AAAA/MX/NS/TXT/CNAME/SOA to map the public infrastructure behind the domain."),
            _t("rdap", "Registration data (registrar, dates, nameservers) establishes age and ownership context."),
            _t("ct_logs", "Certificate transparency reveals publicly issued certificates and additional hostnames."),
            _t("web_fetch", "Fetch the public homepage to capture title, technologies, contacts and outbound links."),
            _t("wayback", "Archive snapshots show how the site, title and contacts changed over time."),
            _t(
                "search_web",
                "Search engines surface public pages, mentions and documents referencing the domain.",
                params={"branches": _search_branches(value, ttype)},
            ),
            _t(
                "github",
                "Public repositories referencing the domain often expose configuration, ownership or integrations.",
            ),
            _t(
                "reddit",
                "Public discussions provide community context; treated as low-tier evidence until corroborated.",
            ),
            _t("search_news", "News coverage gives dated, attributed public statements about the organisation."),
        ]
    elif ttype == TargetType.IP:
        tasks += [
            _t("ip_info", "Reverse DNS, ASN and network ownership from public registries."),
            _t("rdap", "IP RDAP shows the allocation holder and abuse contacts."),
            _t(
                "ct_logs",
                "Certificates issued for hostnames on this address (via reverse DNS) can reveal services.",
                optional=True,
            ),
            _t(
                "search_web",
                "Public mentions (blocklists, reports, documentation).",
                params={"branches": _search_branches(value, ttype)},
            ),
            _t("github", "Code referencing the address may reveal deployments or infrastructure ownership."),
        ]
    elif ttype == TargetType.EMAIL:
        domain = value.split("@")[-1]
        tasks += [
            _t(
                "dns",
                "Mail-domain DNS (MX/SPF/DMARC) confirms whether the domain can receive mail.",
                params={"value": domain},
            ),
            _t("rdap", "Registration data for the mail domain.", params={"value": domain}),
            _t(
                "search_web",
                "Public mentions of the address in pages, repositories and documents.",
                params={"branches": _search_branches(value, ttype)},
            ),
            _t("github", "Public commits and files mentioning the address (secrets are redacted)."),
            _t("reddit", "Public forum mentions.", optional=True),
        ]
    elif ttype in (TargetType.USERNAME, TargetType.SOCIAL_ACCOUNT):
        handle = value.split(":", 1)[-1]
        tasks += [
            _t(
                "social_profiles",
                "Check public profile pages on major platforms for this handle (public data only).",
                params={"handle": handle},
            ),
            _t("github", "GitHub user/organisation and repositories under this handle.", params={"handle": handle}),
            _t("reddit", "Public Reddit account and posts under this handle.", params={"handle": handle}),
            _t(
                "search_web",
                "Search engines find mentions, linked websites and cross-platform references.",
                params={"branches": _search_branches(handle, TargetType.USERNAME)},
            ),
            _t("wayback", "Archived profile pages document historical public bios and links.", optional=True),
        ]
    elif ttype in (TargetType.ORGANIZATION, TargetType.COMPANY):
        tasks += [
            _t(
                "search_web",
                "Identify the official website, domains and public references.",
                params={"branches": _search_branches(value, ttype)},
            ),
            _t("search_news", "News coverage: dated, attributed statements about the organisation."),
            _t("github", "Public organisation accounts and repositories."),
            _t("reddit", "Community discussion (low tier until corroborated)."),
            _t("documents", "Public PDFs/DOCX (reports, filings, presentations) and their metadata.", optional=True),
            _t(
                "research_agent",
                "Expand research on discovered domains and entities within configured bounds.",
                optional=True,
            ),
        ]
    elif ttype == TargetType.PERSON:
        tasks += [
            _t(
                "search_web",
                "Public professional presence, publications and talks (public sources only).",
                params={"branches": _search_branches(value, ttype)},
            ),
            _t("search_news", "Public news mentions."),
            _t("github", "Public code contributions under this name.", optional=True),
            _t("documents", "Public documents authored by or naming the person.", optional=True),
        ]
    elif ttype == TargetType.URL:
        tasks += [
            _t("web_fetch", "Fetch the public page: title, text, metadata, outbound links."),
            _t("wayback", "Historical versions of the page."),
            _t("dns", "Infrastructure of the hosting domain.", params={"from_url": True}),
            _t("search_web", "Pages linking to or discussing this URL.", params={"branches": [f'"{value}"']}),
        ]
    elif ttype == TargetType.CRYPTO_ADDRESS:
        tasks += [
            _t(
                "search_web",
                "Public mentions of the address (forums, repositories, reports).",
                params={"branches": _search_branches(value, ttype)},
            ),
            _t("github", "Repositories referencing the address."),
            _t("reddit", "Forum discussions mentioning the address."),
        ]
    else:
        tasks += [
            _t("search_web", "General public-source research.", params={"branches": _search_branches(value, ttype)})
        ]
    tasks += _common_tail(value)
    branches: list[str] = next((list(t.params.get("branches", [])) for t in tasks if t.task_type == "search_web"), [])
    return Plan(
        objective=objective,
        target_type=str(ttype),
        target_value=value,
        tasks=tasks,
        branches=list(branches),
        source="template",
        rationale=(
            f"Template plan for a {ttype} target. Technical collectors establish verifiable facts first, "
            "search-based collectors add public context, and verification computes confidence from evidence."
        ),
    )
