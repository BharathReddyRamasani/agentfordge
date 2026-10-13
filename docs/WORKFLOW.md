# AgentForge — Workflow

## Prototype validation loop (human-in-the-loop)

```
CREATED → ANALYZING → PLANNING → PROTOTYPE_BUILDING → AWAITING_REVIEW
                                                            ↓  ↖ rebuild (v2, v3…)
                                          CHANGES_REQUESTED → PLAN_REVISION → PROTOTYPE_REBUILDING
                                                            ↓
                                                   APPROVED (explicit only)
```

Feedback always routes through the Planning Agent (revision) before the prototype is
rebuilt. Versions of requirements, plans, prototypes, feedback and approvals persist
with timestamps and user identity. There is no timeout/auto approval.

## Autonomous engineering (post-approval only)

```
APPROVED → ENGINEERING → ARCHITECTURE → DATABASE_DEVELOPMENT → BACKEND_DEVELOPMENT
→ FRONTEND_DEVELOPMENT → INTEGRATION → TESTING ⇄ DEBUGGING (bounded)
→ REVIEW → SECURITY_VALIDATION → DOCUMENTATION → DEPLOYMENT
→ final validation + packaging → COMPLETED
```

`COMPLETED` requires: all generated files present, generated test suite passing,
security verdict pass, ZIPs built. Anything else ends in `FAILED` (with `last_error`)
or `CANCELLED` (at the next stage checkpoint).

## State machine

`orchestrator/state.py:ALLOWED_TRANSITIONS` is the single authority; `transition()`
raises `InvalidTransitionError` on illegal moves (e.g. anything → `ENGINEERING`
without `APPROVED`). Illegal API calls return `409 CONFLICT`, never silent success.

## Observability of progress

- `GET /workflow` — status, stage, %, per-stage states, current agent, last error.
- `GET /agents`, `GET /logs` — task table + event audit trail.
- `GET /events/stream` — SSE with `{event/event_type, project_id, stage, agent,
  message, status, progress, timestamp, payload}`.
- Notifications on prototype-ready, approval, completion, failure.
