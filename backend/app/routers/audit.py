from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import admin_required
from app.enums import AuditAction
from app.models import AuditLog
from app.schemas.audit import AuditLogRead


router = APIRouter(prefix="/audit-logs", tags=["Audit Log"], dependencies=[Depends(admin_required)])


@router.get("", response_model=list[AuditLogRead])
def list_audit_logs(
    action: AuditAction | None = None,
    actor_id: int | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = select(AuditLog)
    if action is not None:
        query = query.where(AuditLog.action == action)
    if actor_id is not None:
        query = query.where(AuditLog.actor_id == actor_id)
    return list(
        db.scalars(query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit))
    )
