"""Workflow event emission: persistent project events + notifications + Redis pub/sub."""

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.events import ProjectEvent
from app.models.notification import Notification

logger = get_logger("agentforge.orchestrator")

TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED"}


def emit_event(
    db: Session,
    project_id: int,
    event: str,
    stage: str = "",
    agent: str = "",
    message: str = "",
    status: str = "ok",
    progress: int | None = None,
    metadata: dict | None = None,
    owner_id: int | None = None,
    notify: bool = False,
    notification_type: str = "info",
) -> ProjectEvent:
    """Record a workflow event (audit trail) and optionally notify the project owner."""
    e = ProjectEvent(
        project_id=project_id,
        stage=stage,
        agent=agent,
        event=event,
        message=message,
        status=status,
        progress=progress or 0,
        metadata_json=metadata,
    )
    db.add(e)
    if notify and owner_id is not None:
        db.add(
            Notification(
                user_id=owner_id,
                project_id=project_id,
                type=notification_type,
                title=message[:200],
                message=message,
            )
        )
    db.commit()
    db.refresh(e)
    _publish(project_id, e)
    logger.info(
        "workflow event",
        extra={
            "project_id": project_id,
            "stage": stage,
            "agent": agent,
            "event": event,
            "status": status,
        },
    )
    return e


def _publish(project_id: int, e: ProjectEvent) -> None:
    """Best-effort Redis publish for real-time consumers (SSE streams poll the DB as fallback)."""
    try:
        from app.workers.queue import get_redis

        payload = {
            "event": e.event,
            "event_type": e.event,
            "project_id": project_id,
            "stage": e.stage,
            "agent": e.agent,
            "message": e.message,
            "status": e.status,
            "progress": e.progress,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        get_redis().publish(f"agentforge:events:{project_id}", json.dumps(payload, default=str))
    except Exception:
        pass
