from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user
from app.enums import AuditAction
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse, UserRead
from app.security import DUMMY_HASH, create_access_token, hash_password, password_needs_rehash, verify_password
from app.services.audit import write_audit


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    return _authenticate(payload.username, payload.password, request, db)


@router.post("/token", response_model=TokenResponse, include_in_schema=True)
def oauth2_token(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """OAuth2 form-compatible token endpoint used by the interactive API docs."""
    return _authenticate(form.username, form.password, request, db)


def _authenticate(username_value: str, password: str, request: Request, db: Session):
    username = username_value.strip()
    user = db.scalar(select(User).where(User.username == username))
    valid = verify_password(password, user.password_hash if user else DUMMY_HASH)
    if user is None or not valid or not user.is_active:
        write_audit(
            db,
            action=AuditAction.LOGIN_FAILED,
            details={"username": username, "reason": "invalid_credentials"},
            request=request,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = datetime.now(UTC)
    write_audit(
        db,
        action=AuditAction.LOGIN,
        actor=user,
        entity_type="user",
        entity_id=user.id,
        request=request,
    )
    token = create_access_token(user_id=user.id, username=user.username, role=user.role.value)
    db.commit()
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)):
    return user
