# API

Base path `/api/v1`. Interactive documentation: `/api/docs` (Swagger) and `/api/redoc`; machine
spec at `/api/openapi.json` (a copy is kept in `packages/schemas/openapi.json`). Errors are JSON
`{code, message, detail}` with analyst-readable messages.

| Area | Endpoints |
|---|---|
| Auth | `GET/POST /auth/setup`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `POST /auth/password`, `GET/POST /auth/users`, `POST /auth/tokens` |
| Health | `GET /health`, `/health/live`, `/health/ready`, `/metrics` |
| Cases | `GET/POST /cases`, `GET/PATCH/DELETE /cases/{id}`, `POST /cases/{id}/clone`, `…/targets`, `…/notes` |
| Investigations | `POST /investigations/start`, `GET /investigations`, `GET /investigations/{id}`, `/status`, `POST /plan` (re-plan), `PATCH /plan`, `POST /tasks`, `POST /approve`, `POST /control {pause|resume|stop}`, `GET /events`, `GET /events/stream` (SSE), `GET /investigations/task-catalogue` |
| Evidence & sources | `GET/POST /cases/{id}/evidence`, `GET /evidence/{id}`, `POST /evidence/{id}/review`, `GET /evidence/{id}/artifacts/{aid}`, `GET /cases/{id}/sources`, `GET /sources`, `GET /sources/{id}`, `/snapshots/{sid}`, `/compare` |
| Entities & graph | `GET/POST /cases/{id}/entities`, `GET /entities/{id}`, `GET/POST /cases/{id}/relationships`, `GET /relationships/{id}` (includes `why`), `POST /relationships/{id}/review`, `GET /cases/{id}/graph?entity_id&depth&types` |
| Findings & timeline | `GET/POST /cases/{id}/findings`, `GET /findings/{id}`, `GET /findings/{id}/why`, `POST /findings/{id}/review`, `POST /findings/{id}/evidence`, `GET /cases/{id}/timeline` |
| Search | `POST /search` (playground; `case_id` stores results), `GET /search/providers`, `POST /search/branches`, `GET /search/cases/{id}/queries|results`, `POST /search/results/{id} {save|ignore|add_evidence|investigate}` |
| AI | `POST /ai/query` (intent routing + cited answer), `GET /ai/cases/{id}/context`, `GET /ai/cases/{id}/retrieve?q=`, `POST /ai/cases/{id}/draft-findings`, `GET /ai/models` |
| Reports & data | `POST /reports`, `GET /reports`, `GET /reports/{id}`, `/download`, `/preview`, `GET /cases/{id}/export?format=`, `POST /cases/{id}/import` |
| Monitoring | `GET/POST /monitors`, `GET/PATCH/DELETE /monitors/{id}`, `POST /monitors/{id}/run`, `GET /alerts`, `POST /alerts/{id}/ack`, `POST /alerts/read-all` |
| System | `GET /audit`, `GET/PATCH /settings`, `GET /collectors`, `GET /dashboard` |

Authentication: cookie session (web) or `Authorization: Bearer eyo_…` (scripts). Non-GET requests
with a cookie session need `X-CSRF-Token`.
