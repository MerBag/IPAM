from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import admin_required
from app.enums import AuditAction, UserRole
from app.models import User
from app.schemas.auth import UserCreate, UserRead, UserUpdate
from app.security import hash_password
from app.services.audit import write_audit


router = APIRouter(prefix="/users", tags=["Users"], dependencies=[Depends(admin_required)])


@router.get("", response_model=list[UserRead])
def list_users(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return list(db.scalars(select(User).order_by(User.username).offset(skip).limit(limit)))


@router.post("", response_model=UserRead, status_code=201)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin_required),
):
    user = User(
        username=payload.username.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=payload.is_active,
    )
    db.add(user)
    try:
        db.flush()
        write_audit(
            db,
            action=AuditAction.USER_CREATED,
            actor=actor,
            entity_type="user",
            entity_id=user.id,
            details={"username": user.username, "role": user.role.value, "is_active": user.is_active},
            request=request,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username already exists")
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    payload: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current: User = Depends(admin_required),
):
    # Serialize role/activation mutations so concurrent admin demotions cannot
    # both observe the other account as the last remaining active admin.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(721149206)"))
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    changes = payload.model_dump(exclude_unset=True)
    changed_fields = sorted(changes)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one field must be supplied")
    was_active_admin = user.role == UserRole.ADMIN and user.is_active
    if user.id == current.id and changes.get("is_active") is False:
        raise HTTPException(status_code=409, detail="You cannot deactivate your own account")
    if "password" in changes:
        password = changes.pop("password")
        if password:
            user.password_hash = hash_password(password)
    for key, value in changes.items():
        setattr(user, key, value)
    removing_last_admin = was_active_admin and (
        changes.get("is_active") is False
        or ("role" in changes and changes["role"] != UserRole.ADMIN)
    )
    if removing_last_admin:
        remaining_active_admins = db.scalar(
            select(func.count(User.id)).where(
                User.id != user.id,
                User.role == UserRole.ADMIN,
                User.is_active.is_(True),
            )
        )
        if remaining_active_admins == 0:
            raise HTTPException(status_code=409, detail="At least one active admin is required")
    write_audit(
        db,
        action=AuditAction.USER_MODIFIED,
        actor=current,
        entity_type="user",
        entity_id=user.id,
        details={"username": user.username, "changed_fields": changed_fields},
        request=request,
    )
    db.commit()
    db.refresh(user)
    return user
