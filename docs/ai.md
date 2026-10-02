# AI (local Ollama)

The AI is an assistant, not an oracle. It runs locally through Ollama and is boxed in by design.

| Component | What the model does | What it cannot do |
|---|---|---|
| Plan adaptation (`ai/planner.py`) | adds up to 4 search branches, disables irrelevant catalogue tasks, writes a rationale | add task types; disable technical/verification tasks for domains |
| Research agent (`ai/agent.py`, `ai/tools.py`) | chooses tool calls: `search_web`, `fetch_public_page`, `search_reddit`, `search_github`, `query_dns`, `query_rdap`, `query_ct_logs`, `search_archive`, `create_evidence`, `create_entity`, `create_relationship`, `verify_claim`, `finish` | fetch URLs that did not come from a tool result; record an excerpt that is not verbatim in the page; create entities not present in the cited evidence; set confidence; run shell commands |
| Summariser (`ai/summarizer.py`) | drafts findings that cite evidence IDs | cite IDs outside the list; invent facts (uncited findings are dropped) |
| Analyst Q&A (`ai/analyst.py`) | answers from retrieved passages with `[EYO-EV-…]` citations | cite unknown IDs (stripped as "unverified reference removed"); answer without passages (replies "Not found in the collected evidence") |
| Intent router (`ai/intents.py`) | deterministic mapping of "show all GitHub references" etc. to structured views | — |

Bounds: `MAX_AGENT_ITERATIONS`, `MAX_RUNTIME_SECONDS` (half for the loop), per-tool call budgets,
analyst pause/stop flags checked every iteration. Every tool call is an `AI_TOOL_CALL` event and an
audit row. Rejected claims are `AI_CLAIM_REJECTED` events.

## Hallucination controls

1. **Quote validation** — `create_evidence` succeeds only if the excerpt is a whitespace-insensitive
   substring of the stored snapshot text (`services/evidence.py::excerpt_in_text`).
2. **URL allow-list** — the agent can only fetch URLs returned by tools in the same run.
3. **Computed confidence** — `verification/confidence.py` assigns labels from evidence; the model's
   opinion is not an input.
4. **Citation checks** — analyst answers and drafted findings are validated against real IDs.
5. **Template fallback** — if Ollama is down or slow, planning uses the template and says so.

## Performance

On a CPU-only workstation `qwen3:8b` produces ~2 tokens/s and takes 60–90 s to load. Eyohe keeps
the model resident (`keep_alive=30m`), uses small contexts for planning, and runs model calls off the
request path. Prefer a smaller model (`OLLAMA_MODEL=qwen3:4b`) if latency matters.
