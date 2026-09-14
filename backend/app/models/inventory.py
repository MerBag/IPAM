from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import DeviceType
from app.models.base import TimestampMixin
from app.models.user import enum_values


class Device(TimestampMixin, Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    type: Mapped[DeviceType] = mapped_column(
        Enum(
            DeviceType,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="device_type",
        ),
        default=DeviceType.OTHER,
        nullable=False,
    )
    management_ip: Mapped[str | None] = mapped_column(String(15), index=True)
    mac_address: Mapped[str | None] = mapped_column(String(17), index=True)
    location: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)

    ip_addresses = relationship("IPAddress", back_populates="device", passive_deletes=True)


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(160))
    email: Mapped[str | None] = mapped_column(String(254))
    phone: Mapped[str | None] = mapped_column(String(50))
    account_reference: Mapped[str | None] = mapped_column(String(100), unique=True)
    notes: Mapped[str | None] = mapped_column(Text)

    ip_addresses = relationship("IPAddress", back_populates="customer", passive_deletes=True)


class Router(TimestampMixin, Base):
    __tablename__ = "routers"
    __table_args__ = (CheckConstraint("api_port BETWEEN 1 AND 65535", name="ck_routers_api_port"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    management_ip: Mapped[str] = mapped_column(String(15), unique=True, nullable=False)
    api_port: Mapped[int] = mapped_column(Integer, default=8728, nullable=False)
    username: Mapped[str | None] = mapped_column(String(128))
    location: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    ip_addresses = relationship("IPAddress", back_populates="router", passive_deletes=True)
