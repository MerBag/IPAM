from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import UserRole
from app.models.base import TimestampMixin


def enum_values(enum_cls):
    return [member.value for member in enum_cls]


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="user_role",
        ),
        default=UserRole.READ_ONLY,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    allocations = relationship("Allocation", back_populates="actor")
    audit_logs = relationship("AuditLog", back_populates="actor")
