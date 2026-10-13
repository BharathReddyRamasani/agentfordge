# AgentForge — Deployment

## Environments

| Mode | DB | Queue | Worker | Secrets |
|---|---|---|---|---|
| Local dev | SQLite (`./data/agentforge.db`) | in-process fallback | in-process thread | dev defaults |
| `docker compose up --build` | PostgreSQL 16 | Redis 7 | thread + `worker` service | `.env` |
| `docker-compose.prod.yml` | PostgreSQL 16 | Redis 7 | `worker` service only | `.env` (prod values) |

## Production start (single command)

```bash
cp .env.example .env        # then set SECRET_KEY, DATABASE_URL (if external),
                            # REDIS_URL (if external), provider keys
docker compose -f docker-compose.prod.yml up --build -d
curl http://localhost:8000/ready
```

## How production differs from dev

- `APP_ENV=production` → demo account seeding disabled.
- No reload/debug flags anywhere (uvicorn runs without `--reload` in all images).
- Migrations run in the image entrypoint (`alembic upgrade head`) before the API/worker start.
- `restart: unless-stopped`, service healthchecks, `postgres`/`redis`/`backend` ordering via
  `depends_on: condition`.
- Persistent volumes: `pgdata`, `redisdata`, `workspace` (generated apps + ZIPs), `ragdata`.
- Resource limits on the worker (compose `deploy.resources.limits`).

## Reverse proxy (recommended)

Terminate TLS in front of `:8000` (nginx/Caddy/Traefik), forward `/` to the backend, set
`CORS_ORIGINS` to the exact frontend origin, and keep `/docs` disabled or firewalled
(`--no-docs` can be added by setting FastAPI `docs_url=None` via env in future; today,
restrict at the proxy).

## Operations

- Health: `GET /health` (liveness) · `GET /ready` (checks DB + queue).
- Logs: structured JSON on stdout (`request_id`, `project_id`, `agent`, `event`, …);
  collect with any log shipper. Secrets are redacted by the formatter.
- Scaling: run more `worker` replicas (jobs are queue-distributed); the API is stateless
  except for local sqlite dev mode (use Postgres when scaling).
