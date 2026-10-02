# Investigations

```
DRAFT → PLANNING → AWAITING_APPROVAL → RUNNING ⇄ PAUSED → VERIFYING → COMPLETED
                                          │                └→ STOPPED / FAILED (resumable)
```

1. **Create** (`POST /api/v1/investigations/start`) with a case, optional target and a natural-
   language request. The target type is classified deterministically (`enrichment/classify.py`).
2. **Plan**: a template per target type (`orchestrator/planner.py`) lists tasks with a rationale
   each; the AI may adapt it (background job, template fallback). Analysts can disable tasks,
   edit search branches and add catalogue tasks before approval.
3. **Approve** (`/approve`): the runner executes enabled tasks in order with cooperative
   pause/stop checks, per-task commits and bounds (`MAX_*`). Each task emits events
   (`TASK_STARTED`, `SOURCE_DISCOVERED`, `EVIDENCE_CREATED`, `ENTITY_DISCOVERED`,
   `RELATIONSHIP_CREATED`, `TASK_COMPLETED` / `TASK_FAILED` / `TASK_SKIPPED`).
4. **Verify**: `correlate` proposes relationships, `verify` recomputes confidence, `summarize`
   drafts AI findings from evidence (skipped honestly if Ollama is unavailable).
5. **Review**: analysts accept/reject/mark evidence, relationships and findings; the decision is
   stored with the reviewer and note, and confidence is recomputed.
6. **Resume**: `COMPLETED`, `STOPPED` and `FAILED` investigations can be resumed; only
   `PENDING`/`FAILED` tasks run again.

`GET /investigations/{id}/status` returns progress, completeness per category (computed from task
state), counts, warnings, errors and remaining tasks. The live feed is `GET
/investigations/{id}/events/stream` (SSE, replay with `?after=<seq>`).

Multi-target cases run one investigation per target; entities and relationships are shared at the
case level, so correlation links them.
