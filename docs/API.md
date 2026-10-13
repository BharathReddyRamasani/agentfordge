# AgentForge — API

Base URL `http://localhost:8000`. Interactive OpenAPI: `/docs` (generated from the
FastAPI route + `response_model` declarations — always in sync with the code).

**Authoritative reference:** `FRONTEND_BACKEND_CONTRACT.md` (26 sections with request/
response examples). This file summarizes the surface for operators.

## Endpoint groups

| Group | Examples |
|---|---|
| Auth | `POST /api/auth/register|login|logout`, `GET /api/auth/me` |
| Projects | `CRUD /api/projects` (paginated `?limit=&offset=`) |
| Prototype loop | `POST .../requirements` → `.../requirements/analyze` → `.../planning` → `.../prototype/generate` → `.../prototype/feedback` ⇄ `.../prototype/approve` |
| Reads | `GET .../analysis`, `.../plan`, `.../planning`, `.../prototype`, `.../prototype/versions`, `.../prototype/preview?token=` |
| Control | `POST .../engineering/start`, `.../cancel`, `.../retry` |
| Observability | `GET .../workflow|agents|logs|memory|testing|debugging|review|security` |
| Deliverables | `GET .../artifacts (+/{id}/download)`, `.../documentation`, `.../deployment`, `.../downloads`, `.../download?type=&token=` |
| Real-time | `GET .../events/stream?token=` (SSE) |
| Misc | `GET /health`, `/ready`, `/readiness`, `/api/notifications` |

## Error envelope (all errors)

```json
{"error": {"code": "CONFLICT", "message": "...", "request_id": "abc123", "details": {}}}
```

Codes: `BAD_REQUEST, UNAUTHENTICATED, FORBIDDEN, NOT_FOUND, CONFLICT,
VALIDATION_ERROR, RATE_LIMITED, INTERNAL_ERROR`. Every response carries `X-Request-ID`.
`422` bodies include per-field details. `409` means an illegal state transition or a
duplicate guarded action (e.g. double approval) — safe to surface directly in UI.
