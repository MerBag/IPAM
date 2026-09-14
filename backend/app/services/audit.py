from fastapi import Request
from sqlalchemy.orm import Session

from app.enums import AuditAction
from app.models import AuditLog, User


def write_audit(
    db: Session,
    *,
    action: AuditAction,
    actor: User | None = None,
    entity_type: str | None = None,
    entity_id: int | str | None = None,
    details: dict | None = None,
    request: Request | None = None,
) -> AuditLog:
    source_ip = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent", "")[:512] if request else None
    log = AuditLog(
        actor_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        details=details or {},
        source_ip=source_ip,
        user_agent=user_agent or None,
    )
    db.add(log)
    return log
