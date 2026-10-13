"""User notifications: workflow updates (approvals, completions, failures)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.workflow import NotificationPublic

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationPublic])
def list_notifications(unread_only: bool = False, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Notification).filter(Notification.user_id == user.id)
    if unread_only:
        query = query.filter(Notification.read.is_(False))
    rows = query.order_by(desc(Notification.id)).limit(100).all()
    return [NotificationPublic(id=r.id, project_id=r.project_id, type=r.type, title=r.title, message=r.message, read=r.read, created_at=r.created_at) for r in rows]


@router.post("/{notification_id}/read", response_model=MessageResponse)
def mark_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user.id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    row.read = True
    db.commit()
    return MessageResponse(status="ok", message="Notification marked as read")
