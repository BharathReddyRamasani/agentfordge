"""AgentForge backend entrypoint: FastAPI application assembly."""

import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, health, notifications, projects, workflow
from app.api.errors import (
    APIError,
    api_error_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.logging import get_logger, setup_logging
from app.core.request_context import request_id_ctx
from app.services import workspace

logger = get_logger("agentforge.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    if settings.app_env == "production" and settings.secret_key == "agentforge-dev-secret-key-change-in-production":
        raise RuntimeError("Refusing to start: SECRET_KEY is still the development default. Set a strong SECRET_KEY in production.")
    Path(settings.workspace_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.rag_dir).mkdir(parents=True, exist_ok=True)
    init_db()
    _recover_stale_job_leases()
    if settings.app_env == "development":
        _seed_demo_user()
    if settings.worker_mode == "thread":
        from app.workers.worker import start_inprocess_worker

        start_inprocess_worker()
        logger.info("in-process worker started", extra={"event": "worker_started"})
    yield
    if settings.worker_mode == "thread":
        from app.workers.worker import stop_inprocess_worker

        stop_inprocess_worker()
        logger.info("in-process worker stopped", extra={"event": "worker_stopped"})


def _recover_stale_job_leases() -> None:
    """A job lease held at startup belonged to a dead process (restart/crash).

    Clear it so cancel/retry report truthfully and interrupted workflows become
    resumable via /retry. Running stages keep their labels; the retry endpoint
    resets stale 'running' markers when resuming.
    """
    from app.models.project import WorkflowState

    db = SessionLocal()
    try:
        stale = db.query(WorkflowState).filter(WorkflowState.job_id.isnot(None)).all()
        for wf in stale:
            logger.warning(
                "clearing stale job lease from previous process",
                extra={"event": "lease_recovered", "project_id": wf.project_id, "error": wf.job_id},
            )
            wf.job_id = None
        if stale:
            db.commit()
    finally:
        db.close()


def _seed_demo_user() -> None:
    """Development convenience only: ensure a demo account exists (never in production)."""
    from app.core.security import hash_password
    from app.models.user import User

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == "demo@agentforge.dev").first()
        if existing is None:
            db.add(User(email="demo@agentforge.dev", name="Demo User", password_hash=hash_password("demo12345")))
            db.commit()
            logger.warning(
                "seeded development demo account demo@agentforge.dev (development only)",
                extra={"event": "demo_seed"},
            )
    finally:
        db.close()


app = FastAPI(title="AgentForge API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    request_id_ctx.set(request_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.middleware("http")
async def secure_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(workflow.router)
app.include_router(notifications.router)


@app.get("/", include_in_schema=False)
def root():
    return {"service": "AgentForge API", "version": "1.0.0", "docs": "/docs"}
