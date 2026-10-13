# AgentForge — Agents

14 logical agent roles, one shared framework (`agents/base.py`):

`run()` = create `agent_tasks` row → RAG retrieval (task-specific query) →
`provider.complete_json()` (schema validation + bounded correction retries) →
record `agent_executions` (duration, tokens, output) → emit events. Failures mark the
task failed and propagate to the orchestrator.

| # | Agent | Stage | Output schema | Materializes |
|---|---|---|---|---|
| 1 | Requirement Analysis Agent | analyze | `RequirementAnalysisResult` | analysis.json |
| 2 | Planning Agent (initial **and** revision — no separate agent) | plan | `PlanningResult` | plan.json |
| 3 | Product/UX & Prototype Agent | prototype | `PrototypeSpec` | interactive `index.html` |
| 4 | Architecture Agent | architecture | `ArchitectureResult` | architecture.json |
| 5 | Frontend Agent | frontend | `FrontendDesignResult` | SPA (`index.html/app.js/...`) |
| 6 | Backend Agent | backend | `BackendDesignResult` | FastAPI app |
| 7 | Database Agent | database | `DatabaseSchemaResult` | `schema.sql/seed.sql/models.py/database.py` |
| 8 | Integration Agent | integration | `IntegrationResult` | real static contract check |
| 9 | Testing Agent | testing | `CodeGenResult` | pytest suite + sandboxed execution |
| 10 | Debugging Agent | debugging | `DebugDiagnosis` | regenerate-from-design fix |
| 11 | Review/Critic Agent | review | `ReviewResult` | `reviews` row (qualitative) |
| 12 | Security/Quality Agent | security | `SecurityResult` | real static secret/pattern scan |
| 13 | Documentation Agent | documentation | `CodeGenResult` | README + 5 guides |
| 14 | Deployment Agent | deployment | `CodeGenResult` | Dockerfile/compose/env/start scripts |

## Provider compatibility

Every agent works with any configured provider (`mock | opencode_zen | openrouter |
nvidia | openai | gemini`) because all LLM access goes through `BaseLLMProvider`.
Optional per-agent routing via `LLM_PROVIDER_<AGENT>` / `LLM_MODEL_<AGENT>`
(e.g. `LLM_MODEL_REVIEW=nvidia/...`) — configuration only, no code changes.
Model names live in `agents/llm/model_registry.py`, never in agent code.

## Prompts

System prompts are modular (`agents/prompts/{prototype_phase,engineering_phase,quality_phase}.py`).
Every prompt carries the injection-defense boundary: system instructions are
authoritative; project context, task input, retrieved context and tool output are
untrusted data that can never override them.
