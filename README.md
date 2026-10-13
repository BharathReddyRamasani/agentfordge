# AgentForge — Autonomous Multi-Agent AI Software Engineering Platform

> **Validate the idea first, then build the application autonomously.**

AgentForge turns a natural-language requirement into a complete application through a
controlled, prototype-first workflow:

```
Requirement → Analysis → Planning → Prototype → Human Review → Approval
→ Full-Scale Autonomous Engineering → Testing → Deployment → Download
```

The prototype validation loop (Plan → Build → Review → Feedback → Revise Plan → Rebuild)
repeats until **explicit human approval**. Only then does autonomous engineering start.
The approved prototype is the source of truth for all 14 specialized agents coordinated by
the Central Orchestrator, with RAG project memory throughout.

**Note:** this repository contains the **backend** (FastAPI + PostgreSQL + Redis + workers).
The product frontend is developed separately and integrates via
[`docs/FRONTEND_BACKEND_CONTRACT.md`](docs/FRONTEND_BACKEND_CONTRACT.md).

## Architecture

```
Manus Frontend (separate) ──REST/SSE──▶ FastAPI backend (:8000)
                                            ├─ 14 agents (analysis→deployment)
                                            ├─ Central Orchestrator (state machine + jobs)
                                            ├─ RAG (per-project vector memory)
                                            ├─ PostgreSQL (18 tables, Alembic)
                                            ├─ Redis (job queue + events; auto fallback)
                                            └─ Worker (thread locally / service in compose)
```

## Quick start (local, no Docker)

Requirements: Python 3.11+, pip.

```powershell
cd agentforge
Copy-Item .env.example .env   # defaults work offline (mock LLM, sqlite, fallback queue)
pip install -r backend/requirements.txt
cd backend
python -m uvicorn app.main:app --port 8000
```

Open `http://localhost:8000/docs`. Login with the seeded dev account
`demo@agentforge.dev / demo12345` (development only).

## Quick start (Docker)

```powershell
cd agentforge
Copy-Item .env.example .env
# set LLM_API_KEY in .env if using a real provider
docker compose up --build
```

Services: `postgres`, `redis`, `backend` (:8000), `worker`. Migrations run automatically.

## Environment

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | SQLAlchemy URL (sqlite local / postgres compose) | `sqlite:///./data/agentforge.db` |
| `REDIS_URL` | Queue (`fakeredis://` forces in-process fallback) | `redis://localhost:6379/0` |
| `LLM_PROVIDER` | `mock` \| `opencode_zen` \| `openrouter` \| `nvidia` \| `openai` \| `gemini` | `mock` |
| `LLM_API_KEY` | Generic provider key (fallback for all providers) | empty |
| `LLM_MODEL` | Model id on the selected provider | `deepseek-v4-flash` |
| `LLM_BASE_URL` | Override endpoint (custom OpenAI-compatible) | empty |
| `LLM_TIMEOUT` / `LLM_MAX_RETRIES` | Per-request timeout (s) / HTTP retry cap | `120` / `2` |
| `OPENCODE_ZEN_API_KEY` | Zen gateway key (or use `LLM_API_KEY`) | empty |
| `OPENROUTER_API_KEY` | OpenRouter key (or use `LLM_API_KEY`) | empty |
| `NVIDIA_API_KEY` | NVIDIA Build/NIM key (or use `LLM_API_KEY`) | empty |
| `LLM_PRIMARY_PROVIDER` / `LLM_FALLBACK_PROVIDER` / `LLM_FALLBACK_MODEL` | Explicit failover (empty = fail clearly) | empty |
| `LLM_MODEL_<AGENT>` | Per-agent model routing, e.g. `LLM_MODEL_REVIEW` | empty |
| `LOG_LEVEL` | `DEBUG`/`INFO`/`WARNING`/`ERROR` | `INFO` |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` | PostgreSQL pool bounds | `5` / `10` |
| `EMBEDDING_PROVIDER` | `tfidf` (local) \| `openai` | `tfidf` |
| `WORKER_MODE` | `thread` (server) \| `external` (compose worker) \| `sync` (tests) | `thread` |
| `SECRET_KEY` | JWT signing secret — **change in production** | dev default |
| `MAX_DEBUG_ITERATIONS` | Testing↔debugging loop cap | `3` |
| `SANDBOX_TIMEOUT` | Generated-code execution timeout (s) | `300` |

## Running tests

```powershell
cd backend
python -m pytest tests/ -q
```

55 tests: auth, state machine, RAG, LLM providers (selection/fallback/normalization/retry),
full prototype-validation loop, approval-gate guards, logout/pagination/error-envelope,
full engineering pipeline to `COMPLETED` (with real generated-code test execution).

## Project structure

```
agentforge/
├── backend/
│   ├── app/
│   │   ├── api/            # auth, projects, workflow, notifications, health
│   │   ├── core/           # config, database, security, logging
│   │   ├── models/         # 18 tables (users…artifacts, notifications)
│   │   ├── schemas/        # agent output contracts + API shapes
│   │   ├── agents/         # 14 agents + llm/ providers + prompts/
│   │   ├── orchestrator/   # state machine, WorkflowRunner engine, events
│   │   ├── rag/            # chunker, embeddings, vector store, pipeline
│   │   ├── tools/          # sandboxed FS/terminal, git, pytest runner, validation
│   │   ├── services/       # workspace isolation, ZIP packaging, codegen/
│   │   └── workers/        # Redis queue + worker loop
│   ├── alembic/            # migrations (verified: 18/18 tables)
│   └── tests/              # 27 tests incl. live E2E
├── workspace/              # generated per-project outputs (git-ignored)
├── docker/ + docker-compose.yml
└── docs/                   # contract + implementation audit
```

## API overview

`POST /api/auth/register|login` · `CRUD /api/projects` · `POST .../requirements` →
`.../requirements/analyze` → `.../planning` → `.../prototype/generate` →
`.../prototype/feedback` ⇄ `.../prototype/approve` → `.../engineering/start` →
`GET .../workflow|agents|logs|memory|testing|debugging|review|security|artifacts|documentation|deployment|downloads|download|events/stream`

Full detail: [`docs/FRONTEND_BACKEND_CONTRACT.md`](docs/FRONTEND_BACKEND_CONTRACT.md).
Audit: [`docs/AGENTFORGE_IMPLEMENTATION_AUDIT.md`](docs/AGENTFORGE_IMPLEMENTATION_AUDIT.md).

## Troubleshooting

- **Port in use:** `uvicorn app.main:app --port 8001` (and set frontend API URL accordingly).
- **Stale dev DB:** delete `data/agentforge.db` (dev sqlite) and restart; migrations re-apply.
- **Redis down locally:** the queue falls back to an in-process backend automatically
  (see `/readiness`); compose provides real Redis.
- **LLM errors:** check `LLM_PROVIDER/LLM_API_KEY/LLM_BASE_URL`; `mock` needs no key.
