"""Authentication routes: registration, login, current user."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.api.deps import audit, bearer_scheme, check_rate_limit, get_current_user
from app.core.database import get_db
from app.core.security import create_access_token, hash_password, verify_password
from app.core.token_blacklist import revoke_token
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.common import MessageResponse, TokenResponse, UserPublic

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(request)
    email = payload.email.strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")
    user = User(email=email, name=payload.name.strip(), password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    audit(db, user.id, None, "user_registered", f"email={email}")
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=UserPublic(id=user.id, email=user.email, name=user.name, created_at=user.created_at))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    check_rate_limit(request)
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    audit(db, user.id, None, "user_login", f"email={email}")
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token, user=UserPublic(id=user.id, email=user.email, name=user.name, created_at=user.created_at))


@router.get("/me", response_model=UserPublic)
def me(user: User = Depends(get_current_user)):
    return UserPublic(id=user.id, email=user.email, name=user.name, created_at=user.created_at)


@router.post("/logout", response_model=MessageResponse)
def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    token = credentials.credentials if credentials else ""
    revoked = revoke_token(token) if token else False
    audit(db, user.id, None, "user_logout", "")
    return MessageResponse(status="ok", message="Logged out" if revoked else "Logged out")
