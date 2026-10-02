# Contributing to Eyohe OSINT

Thanks for helping build an honest intelligence workstation.

## Ground rules
1. **Evidence first.** Every stored fact needs a source, URL/record, timestamp and collector. Code that
   invents, guesses or "fills in" data will not be merged.
2. **Public sources only.** No authentication bypass, paywall/CAPTCHA evasion, scraping of private
   accounts, or intrusive scanning. A 401/403/429 is a result ("not publicly retrievable"), not a hurdle.
3. **The model never decides confidence.** Labels come from `verification/confidence.py`.
4. **Secrets never reach the UI.** Redact in collectors; never log keys.

## Workflow
```bash
make install && make dev
make lint && make typecheck && make test     # must pass before a PR
```
Python: ruff (120 cols) + mypy strict + pytest; TypeScript strict + eslint. Add tests for anything
you touch; mock network calls with `respx`. Schema changes need an Alembic migration.

## Adding a collector
Subclass `BaseCollector`, return a `CollectResult`, register it in `collectors/plugins.py`, add a task
type to `orchestrator/planner.py`, write a mocked test, document it in `docs/collectors.md`.

## Reporting security issues
See [SECURITY.md](SECURITY.md). Please do not open public issues for vulnerabilities.
