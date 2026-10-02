# Collectors

Collectors are plugins (`apps/api/eyohe/collectors/`). They never write to the database: they
return a `CollectResult` (sources, evidence, entities, relationships, timeline items, discovered
targets, warnings) and the orchestrator persists it with provenance (`orchestrator/persist.py`).

```python
class BaseCollector(ABC):
    name: str; description: str; source_tier: int; supported_targets: frozenset[TargetType]; stage: str
    def supports(self, target_type) -> bool
    async def health_check(self) -> CollectorHealth
    async def collect(self, ctx: CollectContext, target_type, value) -> CollectResult
```

Register a new collector by appending an instance to `BUILTIN_COLLECTORS` in `collectors/plugins.py`
and (optionally) adding a task type to `orchestrator/planner.py::TASK_CATALOGUE`.

| Name | Public source | Tier | Produces |
|---|---|---|---|
| `dns` | public resolvers (dnspython) | 3 | A/AAAA/MX/NS/TXT/CNAME/SOA/CAA/DMARC evidence; IP, nameserver, mail-server entities; `RESOLVES_TO`, `USES_NAMESERVER`, `USES_MAIL_SERVER`; null-MX detection |
| `rdap` | rdap.org bootstrap | 3 | registrar, status, nameservers, registration/expiry events (timeline); IP network allocation |
| `ct_logs` | crt.sh | 3 | certificate count, issuers, hostnames → `SUBDOMAIN_OF`; earliest certificate timeline event |
| `ip_info` | reverse DNS + Team Cymru DNS | 3 | PTR, ASN, prefix, registry, country → `HOSTED_ON` |
| `web_fetch` | the public page itself | 1 (target site) / 4 | title, meta, text snapshot, technology indicators, external links, public social profiles, contact addresses; PDF/DOCX/XLSX extraction with metadata |
| `wayback` | Internet Archive CDX | 3 | capture count/range, content-change and title-change timeline, first/latest capture snapshots |
| `github` | api.github.com | 3 | profile (self-declared fields), repositories, repository search, code search (token required) with secret redaction |
| `reddit` | public JSON endpoints | 4 | profile, submissions, search; statements recorded as `PUBLIC_STATEMENT` or `ALLEGATION` |
| `social_profiles` | public profile pages | 4 | presence check on ~20 platforms; records only publicly observable title/description/links; login walls → "not publicly verifiable" |
| search executors (`search_web`, `search_news`, `documents`) | SearXNG / Brave / Serper / Tavily | by domain | result cards as sources, snippets as evidence, top pages fetched via `web_fetch` |

Composite tasks: `correlate` (entity resolution proposals), `verify` (confidence recomputation),
`research_agent` (bounded AI tool loop), `summarize` (AI findings from evidence).

## Politeness and limits

Every request goes through `SafeHttpClient` (SSRF checks, per-host minimum interval, timeouts,
size caps, descriptive User-Agent). API rate limits surface as `CollectorError` with
`retry_after_seconds`, shown in the live feed as e.g. *"GitHub collector failed: API rate limit
reached; retry in 42 seconds"*. Failed tasks can be retried by resuming the investigation.

## What collectors must not do

No authentication, no paywall or CAPTCHA bypass, no anti-bot evasion, no port scanning, no
private-account access. A 401/403/429 is evidence that content is not publicly retrievable, not an
invitation to try harder.
