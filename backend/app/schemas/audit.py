from datetime import datetime

from app.enums import AuditAction
from app.schemas.common import ORMModel


class AuditLogRead(ORMModel):
    id: int
    actor_id: int | None
    action: AuditAction
    entity_type: str | None
    entity_id: str | None
    details: dict
    source_ip: str | None
    user_agent: str | None
    created_at: datetime
