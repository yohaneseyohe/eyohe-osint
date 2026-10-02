# Security

**Authentication** — Argon2id password hashes; opaque session tokens stored as SHA-256 digests in
`sessions`; `HttpOnly`/`SameSite=Lax` cookies (`Secure` when `COOKIE_SECURE=true`); CSRF
double-submit (`eyohe_csrf` cookie echoed in `X-CSRF-Token` for all non-GET requests); bearer API
tokens (`eyo_…`, digest-stored) for scripts; password-change revokes other sessions.

**Authorisation** — roles `admin`, `analyst`, `viewer`; viewers are read-only; settings and user
management require `admin`.

**SSRF** — `core/netsafety.py` validates scheme, forbids embedded credentials, resolves hostnames
and blocks private/loopback/link-local/multicast/reserved/CGNAT ranges, cloud metadata hosts and
internal TLDs, re-validates every redirect hop, caps response size and time. Collectors, the AI
tools and alert webhooks all use it. `ALLOW_PRIVATE_NETWORK_FETCH=true` is only for testing your
own services and is logged.

**Secrets** — kept in `.env`, masked in `/settings`; structured logs pass through a redaction
processor; collected content is scanned and tokens/keys are replaced with `[REDACTED]`; GitHub code
hits containing secrets are stored as "Potential secret detected — redacted".

**Subprocesses** — Chromium is invoked with a fixed argument vector, a temporary profile, no shell
and a timeout. The AI has no shell tool.

**Paths** — evidence/report paths are derived from IDs and verified to stay inside their roots.
Uploads are size-limited and parsed, never executed.

**Rate limiting** — per-IP sliding windows (`RATE_LIMIT_PER_MINUTE`, `AUTH_RATE_LIMIT_PER_MINUTE`),
per-host politeness delays for collectors, per-tool budgets for the AI.

**Audit** — every state change (`CASE_CREATED`, `QUERY_EXECUTED`, `EVIDENCE_CREATED`,
`FINDING_REVIEWED`, `REPORT_GENERATED`, `CONFIG_CHANGED`, `AI_QUERY`, …) is written with actor,
request ID, case and detail.

**Public-source boundaries** — the dork policy refuses credential-hunting queries; collectors treat
401/403/429 as "not publicly retrievable"; identity conclusions require analyst confirmation; the
platform never deanonymises as a definitive claim.
