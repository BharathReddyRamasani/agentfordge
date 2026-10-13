# AgentForge — Frontend/Backend Contract

**Audience:** the separately developed (Manus) frontend. **Backend base URL:** `http://localhost:8000`
(overridable via `NEXT_PUBLIC_API_URL`). Interactive API docs: `http://localhost:8000/docs`.

This document is normative: the backend implements exactly what is described here.
Frontend/backend boundary: the backend owns ALL workflow state; the frontend is a
stateless view over this API and MUST NOT infer authoritative state.

---

## 1. API base URL

```
http://localhost:8000
```

All JSON endpoints below are prefixed with `/api`. Health probes (`/health`, `/ready`, `/readiness`)
are unprefixed.

## 2. Authentication

- Scheme: JWT Bearer. Header: `Authorization: Bearer <access_token>`.
- `POST /api/auth/register` `{email, name, password(min 8)}` → `201 {access_token, token_type: "bearer", user: {id, email, name, created_at}}`
- `POST /api/auth/login` `{email, password}` → `200` same shape. `401` on bad credentials.
- `POST /api/auth/logout` (Bearer) → revokes the token (Redis denylist, TTL = remaining
  lifetime). Reused tokens → `401`.
- `GET /api/auth/me` → `200 {id, email, name, created_at}`. `401` when missing/invalid/expired/revoked.
- Auth endpoints are rate-limited (30 req/min/IP → `429`).
- Endpoints that must work from `<iframe>`, `<a download>` or `EventSource` (no custom
  headers possible) accept the token as a query parameter instead:
  `GET ...?token=<access_token>`. This applies to: prototype preview, artifact download,
  package download, SSE stream. All other endpoints REQUIRE the Bearer header.
- The backend never exposes LLM keys, system prompts or secrets. There is no
  registration captcha; demo account `demo@agentforge.dev / demo12345` exists in
  development only.

## 3. Project endpoints

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/projects` | `{name, description}` | `201 Project` | `401` |
| GET | `/api/projects?limit=100&offset=0` | — | `200 {items: [Project], total}` (total = all owned) | `401` |
| GET | `/api/projects/{id}` | — | `200 Project` | `401, 403 (not owner), 404` |
| DELETE | `/api/projects/{id}` | — | `204` | `401, 403, 404` |

`Project = {id, name, description, status, current_stage, progress (0-100), approved_prototype_version|null, created_at, updated_at, owner_id}`

## 4. Requirement endpoints

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/projects/{id}/requirements` | `{description (10-20000 chars)}` | `201 {id, version, content, status, created_at}` | `401, 403, 422` |
| GET | `/api/projects/{id}/requirements` | — | `200 [{...}] ascending` | `401, 403` |
| POST | `/api/projects/{id}/requirements/analyze` | — | `202 {status: "started"}` (async job) | `401, 403, 409 (wrong state)` |

## 5. Planning endpoints

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/projects/{id}/planning` | — | `202 {status: "started"}` | `401, 403, 409` |
| GET | `/api/projects/{id}/planning` | — | `200 {version, plan: PlanObj, created_at}` (canonical; `/plan` is an alias) | `401, 403, 404 (not ready)` |

`PlanObj = {summary, prototype_scope: {goal, screens: [{name, purpose, sections[]}], interactions[], include[], out_of_scope[]}, full_application_plan: {phases: [{name, description, tasks[]}], stack: {frontend, backend, database}}, feature_priorities: [{feature, priority}], revision_notes}`

## 6. Prototype endpoints

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/projects/{id}/prototype/generate` | — | `202 {status: "started"}` | `401, 403, 409` |
| GET | `/api/projects/{id}/prototype` | — | `200 {id, version, status: built\|validating\|ready\|needs_attention, spec: PrototypeSpec, created_at, versions: [{version, status, created_at}], validation: {version, verdict: pass\|fail, checks: [{name, mandatory, status, detail}]} \| null}` | `401, 403, 404` |
| POST | `/api/projects/{id}/prototype/validate?version=n` | — | `200 {version, verdict, checks, created_at}` — (re)validates a built version without rebuilding | `401, 403, 404` |
| GET | `/api/projects/{id}/prototype/versions` | — | `200 [{version, status, created_at}]` | `401, 403` |
| GET | `/api/projects/{id}/prototype/preview?token=…&version=n` | — | `200 text/html` (self-contained app; `version` optional, default latest) | `401, 404` |

`PrototypeSpec = {app_name, tagline, theme: {primary_color, accent_color, background_color}, screens: [{name, title, sections: [{type: hero|stats|cards|list|form|detail|chart, title, subtitle, items[], fields[{name,label,type,options[]}], stats[{label,value}]}]}], navigation[], user_flow[], features[], sample_data{}, roles[]}`

The served prototype is a working in-browser demo: one shared store seeded from
`sample_data` (lists/cards/stats render from it, so metrics always agree), functional
forms writing to the store, role simulation from `roles`, hash deep-links
(`#screen/<name>`), and a flow-runner checklist. No backend calls; persistence
degrades gracefully inside sandboxed iframes.

Preview response sets `Content-Security-Policy: frame-ancestors 'self' <frontend origins>` so it
is safe to embed in an `<iframe sandbox="allow-scripts allow-forms" src="...preview?token=...">`.

## 7. Feedback endpoint

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/projects/{id}/prototype/feedback` | `{feedback (3-10000 chars)}` | `202 {status: "started"}` — triggers plan revision + rebuild | `401, 403, 409 (not in review), 422` |

Poll `GET /prototype` until `version` increments, or watch the SSE stream.

## 8. Approval endpoint

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/projects/{id}/prototype/approve` | `{comment?, prototype_version?}` — pins the exact version; stale pins → `409` | `200 {status: "approved"}` | `401, 403, 409 (not in review / duplicate / stale / validation-failed)` |

Approval is explicit and recorded (`approved_by, approved_at, prototype_version, comment`).
Only a prototype whose latest automated validation verdict is `pass` may be approved.
Duplicate approval of the same prototype version → `409`. Engineering unlocks only now.

## 9. Engineering endpoint

| Method | Path | Body | Success | Errors |
|---|---|---|---|---|
| POST | `/api/projects/{id}/engineering/start` | — | `202 {status: "started"}` | `401, 403, 409 (not APPROVED)` |
| POST | `/api/projects/{id}/cancel` | — | `200 {status: "cancelling"}` (stops at next checkpoint) | `401, 403, 409 (nothing running)` |
| POST | `/api/projects/{id}/retry` | — | `202 {status: "started"}` (FAILED/CANCELLED only) | `401, 403, 409` |

## 10. Agent endpoint

`GET /api/projects/{id}/agents` → `200 [{agent, stage, status: pending|running|completed|failed, attempts, error|null, started_at, finished_at}]`

Agent names: `Requirement Analysis Agent`, `Planning Agent`, `Product/UX & Prototype Agent`,
`Architecture Agent`, `Frontend Agent`, `Backend Agent`, `Database Agent`, `Integration Agent`,
`Testing Agent`, `Debugging Agent`, `Review/Critic Agent`, `Security/Quality Agent`,
`Documentation Agent`, `Deployment Agent`.

## 11. Workflow endpoint

`GET /api/projects/{id}/workflow` → `200 {status, stage, progress, current_agent|null, stages: [{key, label, status: pending|running|completed|failed|skipped}], last_error|null, cancel_requested, active_job: "<job-id>"|null, started_at, finished_at}`

`active_job` is the job lease: non-null while a background job owns the workflow
(cancel requires it; its absence in a non-terminal, non-waiting state means the
workflow was interrupted and `POST .../retry` will resume it).

## 12. Logs endpoint

`GET /api/projects/{id}/logs?limit=200` → `200 [{id, stage, agent, event, message, status, progress, created_at}]` oldest-first.

## 13. RAG / project-memory endpoint

`GET /api/projects/{id}/memory?q=…&types=a,b&top_k=8` → `200 [{artifact_type, source, version, score, text}]`
relevance-ranked. `types` optionally filters (`requirement, analysis, plan, feedback, prototype,
architecture, backend, frontend, database, test_results, debug_results, documentation, ...`).

## 14. Testing endpoint

`GET /api/projects/{id}/testing` → `200 [{run_id, iteration, total, passed, failed, status: passed|failed|error|timeout, output, created_at}]`

## 15. Debugging endpoint

`GET /api/projects/{id}/debugging` → `200 [{id, run_id, iteration, diagnosis, fix_applied, component, created_at}]`

## 16. Review endpoint

`GET /api/projects/{id}/review` → `200 [{id, iteration, requirement_compliance, architecture_consistency, implementation_completeness, code_quality, verdict, findings: [{severity, area, finding, suggestion}], created_at}]`
(Qualitative fields only — no invented numeric scores.)

## 17. Security endpoint

`GET /api/projects/{id}/security` → `200 [{id, iteration, verdict: pass|fail, critical_issues, checks: [{area, status, detail}], created_at}]`

## 18. Artifact endpoint

`GET /api/projects/{id}/artifacts` → `200 [{id, artifact_type, name, version, stage, size, created_at}]`
`GET /api/projects/{id}/artifacts/{artifact_id}/download?token=…` → file bytes (`404` for directory artifacts).

## 19. Documentation endpoint

`GET /api/projects/{id}/documentation` → `200 [{name, size, path}]` (README.md + docs/*.md inside the generated application).

## 20. Deployment endpoint

`GET /api/projects/{id}/deployment` → `200 [{name, size, path}]` (Dockerfile, docker-compose.yml, .env.example, start scripts).

## 21. Download endpoint

`GET /api/projects/{id}/downloads` → `200 [{kind, filename, size, url}]` with kinds
`prototype, application, docs, deployment, full`.
`GET /api/projects/{id}/download?type=<kind>&token=…` → `200 application/zip`.
`400` on unknown kind.

`GET /api/projects/{id}/application/preview?token=…&path=` → serves the built
full-scale React application (`frontend/dist`, SPA fallback to `index.html`).
`404` when the frontend has not been built yet. Same iframe/CSP rules as the
prototype preview.

## 22. SSE / real-time event contract

`GET /api/projects/{id}/events/stream?token=…` → `text/event-stream`. Each frame:

```json
{"event": "stage_completed", "event_type": "stage_completed", "project_id": 3,
 "stage": "prototype", "agent": "Product/UX & Prototype Agent",
 "message": "Prototype v2 rebuilt", "status": "ok",
 "progress": 45, "timestamp": "2026-10-06T08:00:00+00:00", "payload": {}}
```

Event names: `connected, stage_started, stage_completed, agent_started, agent_completed,
agent_failed, changes_requested, prototype_ready, analysis_completed, engineering_started,
workflow_failed, workflow_cancelled, project_completed`. `status ∈ {ok, error, cancelled}`.
Clients should ALSO poll `GET /workflow` every few seconds as a fallback; the backend is
authoritative either way.

## 23. Error schema

```json
{"error": {"code": "CONFLICT", "message": "...", "request_id": "abc123", "details": {}}}
```

Codes: `BAD_REQUEST (400)` · `UNAUTHENTICATED (401)` · `FORBIDDEN (403)` · `NOT_FOUND (404)` ·
`CONFLICT (409)` · `VALIDATION_ERROR (422, includes per-field `details.fields`)` ·
`RATE_LIMITED (429)` · `INTERNAL_ERROR (500, generic message only)`.
Every response carries an `X-Request-ID` header echoed from the request or generated;
the same id appears in server logs. No stack traces or provider internals are returned.

## 24. Pagination

List endpoints return full arrays (bounded: logs `?limit`, default 200, max 2000; notifications
capped at 100). No cursor pagination in v1.

## 25. Status / state values

Project `status ∈ {CREATED, ANALYZING, PLANNING, PROTOTYPE_BUILDING, AWAITING_REVIEW,
CHANGES_REQUESTED, PLAN_REVISION, PROTOTYPE_REBUILDING, APPROVED, ENGINEERING, ARCHITECTURE,
FRONTEND_DEVELOPMENT, BACKEND_DEVELOPMENT, DATABASE_DEVELOPMENT, INTEGRATION, TESTING,
DEBUGGING, REVIEW, SECURITY_VALIDATION, DOCUMENTATION, DEPLOYMENT, COMPLETED, FAILED, CANCELLED}`.

Stage `status ∈ {pending, running, completed, failed, skipped}`.
Agent task `status ∈ {pending, running, completed, failed}`.

## 26. Request/response examples

```bash
BASE=http://localhost:8000
TOKEN=$(curl -s -X POST $BASE/api/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"dev@example.com","name":"Dev","password":"secret123"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
H="Authorization: Bearer $TOKEN"

PID=$(curl -s -X POST $BASE/api/projects -H "$H" -H 'Content-Type: application/json' \
  -d '{"name":"Hospital Management System","description":"Build a Hospital Management System where patients can register and doctors manage appointments."}' | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

curl -s -X POST $BASE/api/projects/$PID/requirements -H "$H" -H 'Content-Type: application/json' \
  -d '{"description":"Build a Hospital Management System where patients can register, doctors can manage appointments, and admins manage users."}'
curl -s -X POST $BASE/api/projects/$PID/requirements/analyze -H "$H"
curl -s $BASE/api/projects/$PID/analysis -H "$H"
curl -s -X POST $BASE/api/projects/$PID/planning -H "$H"
curl -s -X POST $BASE/api/projects/$PID/prototype/generate -H "$H"
# review at $BASE/api/projects/$PID/prototype/preview?token=$TOKEN, then:
curl -s -X POST $BASE/api/projects/$PID/prototype/approve -H "$H" -H 'Content-Type: application/json' -d '{"comment":"Approved"}'
curl -s -X POST $BASE/api/projects/$PID/engineering/start -H "$H"
curl -s $BASE/api/projects/$PID/workflow -H "$H"
curl -s "$BASE/api/projects/$PID/download?type=full&token=$TOKEN" -o AgentForge_Project.zip
```
