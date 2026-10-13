# AgentForge — Production Readiness

Checked against the implementation (code + 48 tests + live E2E). All items verified,
not claimed.

## SECURITY
- [x] no hardcoded secrets (env-only; `.env` git-ignored; tests assert no plaintext passwords)
- [x] authentication secure (bcrypt + expiring JWT + logout denylist)
- [x] authorization enforced (ownership on every project route; 403 tested)
- [x] generated code sandboxed (subprocess jail, secret-stripped env, timeout, traversal guard)
- [x] input validation (Pydantic everywhere; 422 envelope with fields)
- [x] safe file handling (WorkspaceFS sandbox; downloads by id, never raw paths)
- [x] prompt injection defenses (separated prompt sections in every agent)
- [x] secure downloads (owner-checked, token-authed)

## RELIABILITY
- [x] persistent workflow state (DB-backed stages; survives restarts; retry resumes)
- [x] retries bounded (provider HTTP backoff cap; validation retries; debug-loop cap)
- [x] timeouts (LLM timeout, sandbox timeout, queue poll, worker shutdown join)
- [x] recovery (FAILED/CANCELLED → /retry; worker crash loop with backoff)
- [x] graceful failure (FAILED + last_error + notification; never fake success)
- [x] worker recovery (standalone loop; in-process stop event on shutdown)
- [x] idempotency (duplicate approval rejected; retry maps to earliest incomplete phase)

## DATA
- [x] migrations (Alembic 0001; verified 18/18 tables)
- [x] indexes, relationships, cascading deletes, timestamps, versioning, ownership

## AI
- [x] provider abstraction (BaseLLMProvider; zen/openrouter/nvidia/openai/gemini/mock)
- [x] structured outputs (schema validation + correction retries; native JSON mode where supported)
- [x] RAG (chunk→embed→rank→select; per-project isolation; /memory endpoint)
- [x] orchestration (state-machine engine; 14 agents; events + audit)

## INFRASTRUCTURE
- [x] Docker (backend image; dev + prod compose; entrypoint migrations)
- [x] PostgreSQL, Redis, workers, health + readiness probes, production config

## API
- [x] REST + auth + consistent envelope errors + OpenAPI + SSE + frontend contract

## PRODUCT
- [x] complete workflow: requirement → … → approval gate → engineering → testing →
      debugging → review → security → docs → deployment → downloads (live-tested)
