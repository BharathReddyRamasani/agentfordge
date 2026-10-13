"""Shared API dependencies: authentication (header or query token), project ownership,
audit logging, and a lightweight auth rate limiter."""

import time
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.events import AuditLog
from app.models.project import Project
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)

# Simple in-memory rate limiter for auth endpoints (per client IP)
_rate_buckets: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT = 30
RATE_WINDOW_S = 60.0


def check_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    bucket = [t for t in _rate_buckets[ip] if now - t < RATE_WINDOW_S]
    _rate_buckets[ip] = bucket
    if len(bucket) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail="Too many requests, please slow down")
    bucket.append(now)


def _user_from_token(token: str | None, db: Session) -> User:
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    from app.core.token_blacklist import is_revoked

    if is_revoked(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked (logged out)")
    subject = decode_access_token(token)
    if subject is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    try:
        user_id = int(subject)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    return _user_from_token(credentials.credentials if credentials else None, db)


def get_current_user_flexible(request: Request, db: Session = Depends(get_db)) -> User:
    """Accept a Bearer header OR a ?token= query parameter (needed for iframe/SSE/downloads)."""
    token = None
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
    if not token:
        token = request.query_params.get("token")
    return _user_from_token(token, db)


def get_owned_project(project_id: int, user: User, db: Session) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != user.id:
        raise HTTPException(status_code=403, detail="You do not own this project")
    return project


def audit(db: Session, user_id: int | None, project_id: int | None, action: str, detail: str = "") -> None:
    db.add(AuditLog(user_id=user_id, project_id=project_id, action=action, detail=detail[:2000]))
    db.commit()
