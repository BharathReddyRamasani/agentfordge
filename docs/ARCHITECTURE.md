# AgentForge — Architecture

## System overview

```
Manus React frontend (separate repo)
   │  REST + SSE  (see FRONTEND_BACKEND_CONTRACT.md)
   ▼
FastAPI backend (app/main.py, :8000)
   ├─ api/            auth · projects · workflow · notifications · health
   ├─ agents/         14 specialized agents, shared BaseAgent framework
   │    └─ llm/      BaseLLMProvider → mock | opencode_zen | openrouter |
   │                                   nvidia | openai | gemini (+explicit fallback)
   ├─ orchestrator/  state machine + WorkflowRunner engine + events
   ├─ rag/           chunker → embeddings → per-project vector store → ranked retrieval
   ├─ tools/         sandboxed FS · restricted terminal · git · pytest runner · validation
   ├─ services/      workspace isolation · ZIP packaging · codegen (prototype/app/docs)
   ├─ workers/       Redis queue + worker loop (thread / external / sync)
   ├─ PostgreSQL    18 tables via Alembic (prod) / SQLite (dev/tests)
   └─ Redis          job queue + event pub/sub (+ in-process fallback)
```

## Key design decisions

- **Backend owns all workflow state.** The frontend is stateless; every transition is
  validated by `orchestrator/state.py` and persisted before events are emitted.
- **Agents share the provider runtime, not prompts.** Each agent keeps its own system
  prompt (`agents/prompts/`), output schema (`schemas/`), and RAG retrieval policy.
- **Designs via LLM, materialization via deterministic codegen.** LLM output can never
  break runnability: code generators (`services/codegen/`) synthesize the runnable
  prototype HTML and the generated application from validated designs.
- **Prototype-first gate.** `AWAITING_REVIEW` only exits via explicit `approve`
  (→ `APPROVED`) or `feedback` (→ revision loop). Engineering endpoints enforce
  `APPROVED`; the state machine has no path around it.
- **Per-project isolation.** `workspace/{project_id}/` holds `prototype/`,
  `application/` (self-contained runnable tree), `artifacts/` (+JSON +ZIPs).
  `WorkspaceFS` blocks path traversal; generated code never runs in-process.
- **RAG is per-project namespaced.** Retrieval is always filtered by `project_id`;
  cross-project leakage is impossible by construction.

## Request lifecycle (writes)

`API → auth/ownership → state validation → enqueue job → 202 → worker runs
WorkflowRunner → agents (RAG context → provider → validated output) → DB commits per
stage → events + notifications → /workflow|logs|stream reflect progress.`

## Failure model

Stage failures mark the project `FAILED` with `last_error`; nothing is silently
swallowed. `FAILED`/`CANCELLED` resume via `/retry` to the earliest incomplete phase.
Testing↔debugging is bounded by `MAX_DEBUG_ITERATIONS`; provider fallback only fires
for transient/model errors and only when explicitly configured.
