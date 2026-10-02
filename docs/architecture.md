# Eyohe OSINT — Architecture

> **Public Intelligence. Connected Evidence.**
> A local-first intelligence-analysis workstation for legitimate public-source investigations.

This document is the authoritative architecture reference. It covers the final technology
choices, repository layout, service boundaries, data model, AI agent design, collector plugin
architecture, security architecture, the investigation state machine, and the delivery roadmap.
Where this deviates from the original specification, the reason is stated.

---

## 1. Design principles

1. **Every conclusion must be traceable to evidence.** Findings reference evidence IDs;
   evidence references source snapshots; snapshots carry URL, timestamp, hash, and collector.
2. **Never fabricate.** The LLM never produces a source, URL, date, quote, or relationship that
   does not come from a tool result. Quotations are validated as substrings of the collected text.
3. **Public-source only.** No authentication bypass, no CAPTCHA/anti-bot evasion, no private data.
4. **Local-first and resource-aware.** Must run on 16 GB RAM. Heavy services are optional.
5. **Human-in-the-loop for identity conclusions.** The system proposes; the analyst decides.

---

## 2. Technology choices (final)

| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 15 (App Router), React 19, TypeScript strict, Tailwind v4, shadcn-style components, `@xyflow/react`, Recharts, TanStack Query, Zustand | Spec-preferred stack; mature; good density for analyst UIs |
| API | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (async) | Spec-preferred; async I/O suits collectors |
| Database | PostgreSQL 16 (primary), SQLite (dev fallback) | Normalized schema; PG full-text search for retrieval |
| Migrations | Alembic | Every schema change is a migration |
| Cache / queue | Redis 7 | Query cache, rate-limit counters, event fan-out |
| Background jobs | **`arq`** worker, with an **embedded** asyncio runner for development | See decision D1 |
| Graph | PostgreSQL tables by default; Neo4j optional adapter (`GRAPH_BACKEND`) | Spec requirement; Neo4j is RAM-heavy |
| Local AI | Ollama (`/api/chat` with tools, `format=json` for plans) | Model configurable (`OLLAMA_MODEL`) |
| Search | SearXNG (self-hosted, Compose profile `search`), Brave / Serper / Tavily connectors | Keyed connectors raise a configuration error when the key is missing. No fake results |
| PDF | WeasyPrint when importable, else headless Chromium `--print-to-pdf` | Both available on Kali; no cloud |
| DOCX | python-docx | |
| Screenshots | Headless Chromium via safe subprocess (fixed argv, no shell) | No Playwright download; works offline |
| Reverse proxy | Caddy | Automatic local TLS, simple config |
| Logging | structlog JSON | request_id / case_id / task_id bound to context |
| Metrics | prometheus-client at `/metrics` | |
| Package mgmt | `uv` (Python), `npm` (Node) | Fast, reproducible |

### Decisions that change the specification

**D1 — `arq` instead of Celery.** Celery is synchronous-first and heavy for a single workstation.
`arq` is a small Redis-backed async job runner that fits an all-async collector stack. For local
development the API can run jobs in-process (`JOB_BACKEND=embedded`) so the acceptance workflow
works with only PostgreSQL (or SQLite) running. Switching to `JOB_BACKEND=arq` starts a separate
worker container. Both backends execute the exact same `InvestigationRunner` code.

**D2 — Deterministic plan templates + LLM rationale.** Investigation plans are generated from
target-type templates (so the system is predictable and works when Ollama is down) and the LLM is
asked to *adapt* the plan (add/remove/reorder branches, generate queries) and *explain* each task.
The LLM can never add a task type that is not a registered tool. This prevents plan hallucination.

**D3 — Quote validation as hallucination control.** When the LLM extracts a claim with an
excerpt from a page, the excerpt must be a (whitespace-normalized) substring of the stored
snapshot text; otherwise the claim is rejected and an `AI_CLAIM_REJECTED` event is recorded.

**D4 — Confidence is computed, not asserted.** Confidence labels are derived by a rule engine
from the evidence attached to a finding: number of *independent* sources, source tiers,
evidence types, and the presence of contradicting evidence. The LLM may propose a label but the
engine's label wins and the UI shows the computed rationale ("Why?").

**D5 — Services live in one Python package.** `services/*` in the spec are implemented as
sub-packages of `apps/api/eyohe/` (orchestrator, collectors, enrichment, verification,
reporting, scheduler). They share the ORM models and config, and run either in the API process
or in the worker. Splitting them into separate deployables on a 16 GB laptop adds latency and RAM
without a benefit. The package boundaries are kept strict so they can be extracted later.

---

## 3. Repository structure

```
eyohe-osint/
├── apps/
│   ├── api/                      # FastAPI + orchestrator + collectors + reporting + worker
│   │   ├── eyohe/
│   │   │   ├── core/             # config, logging, security, db session, ids, errors
│   │   │   ├── models/           # SQLAlchemy ORM (one file per aggregate)
│   │   │   ├── schemas/          # Pydantic request/response models
│   │   │   ├── api/v1/           # routers
│   │   │   ├── services/         # domain services (cases, evidence, entities, findings…)
│   │   │   ├── collectors/       # BaseCollector + plugins (dns, rdap, ct, github, reddit…)
│   │   │   ├── search/           # providers, query generation, normalization, dedupe
│   │   │   ├── orchestrator/     # planner, runner, tool registry, agent loop, state machine
│   │   │   ├── ai/               # Ollama client, prompts, structured output, guards
│   │   │   ├── enrichment/       # entity extraction, resolution, timeline building
│   │   │   ├── verification/     # confidence engine, source comparison
│   │   │   ├── reporting/        # renderers: markdown, html, pdf, docx; templates
│   │   │   ├── scheduler/        # monitors, alerts, arq cron
│   │   │   ├── graph/            # GraphBackend interface: postgres + neo4j
│   │   │   └── worker.py         # arq worker entrypoint
│   │   ├── alembic/
│   │   └── tests/
│   └── web/                      # Next.js workstation UI
├── packages/schemas/             # OpenAPI export → TS client types
├── infrastructure/{docker,caddy,scripts}
├── data/{evidence,reports,screenshots,exports,cache}
├── docs/
├── docker-compose.yml
├── Makefile
└── .env.example
```

---

## 4. Database design (ERD summary)

All tables use UUID primary keys, `created_at`/`updated_at` timestamps (UTC), and human-readable
`display_id` where analysts need to cite them (`EYO-CASE-000001`, `EYO-EV-000042`,
`EYO-FND-000007`, `EYO-ENT-…`, `EYO-SRC-…`).

```
users ─< sessions
users ─< audit_logs

cases ─< targets
cases ─< investigations ─< investigation_tasks
                        └< investigation_events
cases ─< sources ─< source_snapshots
cases ─< evidence ─< evidence_artifacts
evidence >─ sources (nullable)
cases ─< entities ─< entity_aliases
cases ─< relationships (src_entity, dst_entity) ─< relationship_evidence >─ evidence
cases ─< findings ─< finding_evidence >─ evidence
cases ─< timeline_events >─ evidence (nullable)
investigations ─< search_queries ─< search_results >─ sources (nullable)
cases ─< notes
cases ─< reports ─< report_sections
cases ─< monitors ─< alerts
system_settings (key/value, server-side only)
```

Indexes: `sources.canonical_url` (unique per case), `entities(case_id, type, normalized_value)`
(unique), `evidence(case_id)`, `investigation_events(investigation_id, seq)`,
`audit_logs(created_at)`, `search_results(canonical_url)`, and GIN full-text indexes on
`evidence.excerpt`, `notes.body`, `source_snapshots.text_content` (PostgreSQL only).

Key enumerations (stored as strings for migration friendliness):

- `CaseStatus`: DRAFT, ACTIVE, PAUSED, COMPLETED, ARCHIVED
- `InvestigationStatus`: DRAFT, PLANNING, AWAITING_APPROVAL, RUNNING, PAUSED, VERIFYING,
  COMPLETED, STOPPED, FAILED
- `TaskStatus`: PENDING, RUNNING, COMPLETED, FAILED, SKIPPED, DISABLED
- `Confidence`: CONFIRMED, CORROBORATED, SUPPORTED, POSSIBLE, INFERENCE, UNVERIFIED, CONTRADICTED
- `EvidenceType`: DIRECT_STATEMENT, TECHNICAL_RECORD, DOCUMENT, PUBLIC_STATEMENT, ALLEGATION,
  SYSTEM_INTERPRETATION, ARCHIVE_SNAPSHOT
- `ReviewState`: PENDING, ACCEPTED, REJECTED, NEEDS_VERIFICATION
- `SourceTier`: 1..5 (official primary → unverified)
- `EntityType`: PERSON, USERNAME, EMAIL, DOMAIN, IP, URL, ORGANIZATION, COMPANY, LOCATION, PHONE,
  SOCIAL_ACCOUNT, REPOSITORY, DOCUMENT, ARTICLE, EVENT, CRYPTO_ADDRESS, ASN, CERTIFICATE
- `RelationshipType`: MENTIONS, LINKS_TO, OWNS, AUTHORED, REFERENCES, HOSTED_ON, RESOLVES_TO,
  ASSOCIATED_WITH, POSSIBLY_SAME_ENTITY, CONFIRMED_BY_SOURCE

---

## 5. Service architecture

```
 Browser ──HTTPS──> Caddy ──> Next.js (UI)  ──/api/*──> FastAPI
                                                  │
                     ┌────────────────────────────┼─────────────────────────┐
                     │   Domain services          │   Orchestrator          │
                     │   cases/evidence/entities  │   planner → runner      │
                     │   findings/timeline/notes  │   tool registry         │
                     │   reports/monitors         │   agent loop (Ollama)   │
                     └──────────┬─────────────────┴──────────┬──────────────┘
                                │ SQLAlchemy                 │ collectors (httpx, dnspython)
                           PostgreSQL                   Public Internet
                                │                             │
                           Redis (cache, rate-limit, events)  │
                                │                             │
                      arq worker (JOB_BACKEND=arq) ───────────┘
```

**Event flow.** Collectors emit `InvestigationEvent` rows (append-only, monotonically numbered
per investigation). The API streams them to the UI with Server-Sent Events. In embedded mode an
in-process broadcaster pushes events; in `arq` mode the worker publishes to a Redis channel the
API subscribes to. The SSE endpoint always replays from the last seen `seq`, so reconnects and
reloads never lose events and nothing is ever synthesized for display.

---

## 6. AI agent architecture

```
UserRequest ─> ObjectiveExtractor ─> TargetClassifier ─> Planner ─> (analyst approval)
                                                             │
                                                     InvestigationRunner
                                                             │
                           ┌─────────────── per task ────────┴──────────────┐
                           │  Collector tool  →  Normalizer  →  Evidence     │
                           │  Entity extractor →  Resolver  →  Relationships │
                           └─────────────────────────────────────────────────┘
                                                             │
                                               ResearchAgent (tool loop, bounded)
                                                             │
                                                   Verification engine
                                                             │
                                                     Findings + Report
```

- **Tools** are Python callables with Pydantic input/output schemas, a permission boundary,
  timeout, rate limit, and an audit event. The LLM only sees the registered tool schemas.
  `search_web`, `fetch_public_page`, `search_reddit`, `search_github`, `query_dns`, `query_rdap`,
  `query_ct_logs`, `search_archive`, `extract_document`, `create_evidence`, `create_entity`,
  `create_relationship`, `verify_claim`, `generate_report`.
- **Bounds**: `MAX_AGENT_ITERATIONS`, `MAX_RESEARCH_DEPTH`, `MAX_QUERIES`, `MAX_PAGES`,
  `MAX_RUNTIME_SECONDS`, `MAX_RESULTS_PER_SOURCE`. The runner checks a cooperative stop/pause
  flag (DB + Redis) between tool calls.
- **Guards**: quote validation (D3), URL allow-list (only URLs that came back from a tool may be
  fetched), structured-output validation, and a "no new facts" rule in report writing: the
  report writer receives only evidence/findings and must cite IDs; uncited sentences are flagged.
- **Case memory / RAG**: PostgreSQL full-text search over evidence, notes, snapshots and findings
  (pgvector optional later). The analyst panel retrieves top-k passages for a question and sends
  only those to the model.

---

## 7. Collector / plugin architecture

```python
class BaseCollector(ABC):
    name: str                 # "dns", "rdap", "ct", "github", "reddit", "wayback", "searxng"...
    source_tier: int          # default tier for sources it produces
    def supports(self, target: Target) -> bool
    async def health_check(self) -> CollectorHealth
    async def collect(self, ctx: CollectContext, target: Target) -> CollectResult
    def normalize(self, raw) -> list[NormalizedItem]
    def validate(self, item) -> bool
```

A registry discovers collectors, exposes their health to `/api/v1/health`, and the planner maps
task types to collectors. Collectors never write to the DB directly; they return normalized items
and the runner persists sources, snapshots, evidence and entities with provenance. Every outbound
HTTP request goes through `SafeHttpClient`, which enforces SSRF rules, timeouts, size limits,
a shared User-Agent, and per-host rate limits.

---

## 8. Security architecture

- **Auth**: Argon2id password hashing; opaque session tokens (DB-backed) in `HttpOnly`,
  `SameSite=Lax`, `Secure` (behind TLS) cookies; CSRF double-submit header for unsafe methods;
  optional API tokens for scripts. RBAC roles: `admin`, `analyst`, `viewer`.
- **SSRF**: URL validation rejects non-http(s) schemes, credentials in URLs, literal and
  DNS-resolved private/loopback/link-local/multicast/reserved ranges, cloud metadata hosts, and
  `.internal`/`.local` suffixes; redirects are re-validated hop by hop. `ALLOW_PRIVATE_NETWORK_FETCH`
  exists only for explicit local testing and is logged loudly.
- **Secrets**: `.env` only; never returned by the settings API (masked); redaction filter in logs;
  secret-pattern scanner redacts tokens found in collected content before storage.
- **Subprocess**: Chromium is invoked with a fixed argv, no shell, timeout, and sandboxed
  profile directory. No LLM-controlled shell access exists.
- **Paths**: artifact paths are derived from IDs, never from user input; evidence vault roots are
  resolved and checked with `is_relative_to`.
- **Rate limiting**: per-IP for auth endpoints, per-user for API, per-host for collectors.
- **Audit**: every state-changing action writes an `audit_logs` row with actor and request id.

---

## 9. Investigation state machine

```
DRAFT ──start──> PLANNING ──plan ready──> AWAITING_APPROVAL ──approve──> RUNNING
                     │                            │                         │  ├─pause─> PAUSED ─resume─┐
                     └──error──> FAILED           └──reject──> DRAFT        │  │                        │
                                                                            │  └────────────────────────┘
                                                               tasks done ──┴──> VERIFYING ──> COMPLETED
                                                               analyst stop ──> STOPPED  (resumable → RUNNING)
                                                               unrecoverable  ──> FAILED   (resumable → RUNNING)
```

State is persisted on every transition; the runner is idempotent per task (tasks have their own
status) so a resumed investigation only executes PENDING/FAILED tasks.

---

## 10. Development roadmap

| Phase | Scope | Exit criteria |
|---|---|---|
| 1 | Repo, config, DB, auth, API shell, UI shell, Compose, Makefile, setup script | `make test`, login works, health page green |
| 2 | Cases, targets, investigations, events (SSE), evidence, entities, findings, audit | CRUD + SSE verified in UI |
| 3 | Search infra: providers, query generation, normalization, dedupe, caching | Unit tests + playground |
| 4 | Collectors: DNS, RDAP, CT, Wayback, GitHub, Reddit, News, page fetcher, documents | Each collector has health + tests |
| 5 | AI investigator: planner, tool registry, bounded loop, quote guard, verification | End-to-end run on `example.com` |
| 6 | Entity extraction, resolution, relationships, graph backend, timeline | Graph API returns evidence-backed edges |
| 7 | Workstation UI: dashboard, workspace, live feed, graph, timeline, evidence review, Why? | Acceptance steps 1–18 |
| 8 | Reporting: Markdown, HTML, PDF, DOCX with evidence index | PDF contains source URLs and evidence IDs |
| 9 | Monitoring, alerts, scheduled re-runs, notifications | Monitor produces a real alert |
| 10 | Hardening, tests, performance, docs, deployment | Full acceptance test passes |
