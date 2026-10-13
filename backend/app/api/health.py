"""Health and readiness probes."""

from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import SessionLocal

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {"status": "ok", "service": "agentforge-backend"}


@router.get("/ready")
def ready():
    """Liveness/readiness alias for orchestrators that probe /ready."""
    return readiness()


@router.get("/readiness")
def readiness():
    checks = {"database": "unknown", "queue": "unknown"}
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            checks["database"] = "ok"
        finally:
            db.close()
    except Exception as exc:
        checks["database"] = f"error: {str(exc)[:200]}"
    try:
        from app.workers.queue import get_redis

        get_redis().ping()
        checks["queue"] = "ok"
    except Exception as exc:
        checks["queue"] = f"error: {str(exc)[:200]}"
    ready = all(v == "ok" for v in checks.values())
    return {"ready": ready, "checks": checks}
