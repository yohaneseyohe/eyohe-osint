<p align="center">
  <strong style="font-size:1.6em;letter-spacing:.2em">EYOHE OSINT</strong><br>
  <em>Public Intelligence. Connected Evidence.</em>
</p>

Eyohe OSINT is a **local-first intelligence-analysis workstation** for legitimate public-source
investigations. You describe an investigation in plain language; Eyohe turns it into a plan of
collection tasks, runs public-source collectors, extracts entities, links them with
evidence-backed relationships, computes confidence from the evidence, and produces reports in
which every claim traces back to a source, a URL and a timestamp.

> **Every conclusion must be traceable back to evidence.** Nothing is fabricated: when a source is
> not configured the task is skipped and says so; when a quote cannot be found in the fetched page
> it is rejected; when evidence is thin the finding says `POSSIBLE` or `UNVERIFIED`.

## What it does

| Area | Capability |
|---|---|
| Investigation engine | Request → target classification → plan (template, optionally adapted by a local Ollama model) → analyst approval → bounded execution with pause/resume/stop → verification |
| Collectors (plugins) | DNS, RDAP/WHOIS, certificate transparency, IP/ASN, public web pages (fingerprint, links, contacts, documents), Wayback Machine history, GitHub, Reddit, public social-profile presence, search engines (SearXNG, Brave, Serper, Tavily), news, public documents (PDF/DOCX/XLSX metadata) |
| Evidence model | Sources with snapshots and SHA-256; evidence with claim, verbatim excerpt (validated), collector, timestamps, review state; immutable-ish records in a local **evidence vault** |
| Entity intelligence | Deterministic extraction, evidence-backed relationships, conservative resolution (`POSSIBLY_SAME_ENTITY` is never auto-confirmed), graph API (PostgreSQL by default, Neo4j optional) |
| Confidence | Rule engine: `CONFIRMED · CORROBORATED · SUPPORTED · POSSIBLE · INFERENCE · UNVERIFIED · CONTRADICTED`, with a **Why?** chain for every finding and relationship |
| AI analyst (Ollama) | Plan adaptation, a bounded tool-calling research loop with URL allow-listing and quote validation, evidence-only finding drafts, cited Q&A over the case; never sets confidence, never invents sources |
| Live feed | Append-only investigation events streamed over SSE with replay |
| Reporting | Markdown, HTML, PDF, DOCX with executive summary, findings (supporting/contradicting evidence IDs), entities, graph, timeline, source analysis, evidence index, limitations, methodology, references |
| Monitoring | Scheduled re-collection with baseline diffing → typed alerts (in-app, Telegram, webhook, email) |
| Governance | Argon2 auth, DB sessions + CSRF, RBAC, rate limiting, SSRF-safe fetching, secret redaction, audit log, exports/imports, backups |

## Quick start (Kali / Debian / Ubuntu)

```bash
git clone <this repo> eyohe-osint && cd eyohe-osint
make setup                      # detects Python/uv/Node/Docker/Ollama/Chromium, writes .env,
                                # and picks PostgreSQL if it is running, otherwise SQLite
make install                    # uv sync (API) + npm install (web)
docker compose --profile search up -d searxng     # recommended search provider (self-hosted)
make migrate
make dev                        # API http://127.0.0.1:8000  ·  UI http://localhost:3000
```

Open http://localhost:3000, complete the first-run wizard (health check → admin account), create a
case, add a target such as `example.com`, start an investigation, approve the plan and watch the
live feed. Then open **Findings → Why?**, the **Graph**, and generate a **PDF report**.

Minimum footprint: PostgreSQL (or SQLite), the API and the web app. Redis, SearXNG, the arq worker
and Neo4j are optional and start only when you enable them. Ollama runs on the host.

## Repository layout

```
apps/api      FastAPI + orchestrator + collectors + AI + reporting + scheduler (Python 3.12, uv)
apps/web      Next.js workstation UI (TypeScript strict, Tailwind, React Flow)
docs/         architecture, installation, configuration, collectors, ai, evidence, investigations,
              reporting, security, database, API, development
infrastructure/  docker, caddy, scripts (setup, dev, backup, restore)
data/         evidence vault, reports, screenshots, exports, cache (local only)
```

Start with [docs/architecture.md](docs/architecture.md) and [docs/installation.md](docs/installation.md).

## Legal and safety boundaries

Eyohe OSINT researches **public sources only**. It does not bypass authentication, paywalls,
CAPTCHAs or anti-bot controls; does not scrape private accounts or messages; redacts secrets found
in public code; refuses credential-hunting search operators; and never states an identity
conclusion as fact without analyst confirmation. See [docs/security.md](docs/security.md).

## Status

Phases 1–9 of the build plan are implemented with 90+ automated tests (unit, integration and an
offline end-to-end acceptance workflow). See `make test`, `make lint`, `make typecheck`.

MIT License.
