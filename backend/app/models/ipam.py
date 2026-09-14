from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.enums import AllocationAction, IPStatus, SubnetStatus
from app.models.base import TimestampMixin
from app.models.user import enum_values


class Prefix(TimestampMixin, Base):
    __tablename__ = "prefixes"
    __table_args__ = (
        CheckConstraint("prefix_length BETWEEN 0 AND 32", name="ck_prefixes_prefix_length"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cidr: Mapped[str] = mapped_column(String(18), unique=True, index=True, nullable=False)
    network_address: Mapped[str] = mapped_column(String(15), nullable=False)
    broadcast_address: Mapped[str] = mapped_column(String(15), nullable=False)
    prefix_length: Mapped[int] = mapped_column(Integer, nullable=False)
    first_usable_ip: Mapped[str] = mapped_column(String(15), nullable=False)
    last_usable_ip: Mapped[str] = mapped_column(String(15), nullable=False)
    network_int: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    broadcast_int: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    total_addresses: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    subnets = relationship("Subnet", back_populates="prefix", cascade="all, delete-orphan")
    ip_addresses = relationship("IPAddress", back_populates="prefix", cascade="all, delete-orphan")


class Subnet(TimestampMixin, Base):
    __tablename__ = "subnets"
    __table_args__ = (
        UniqueConstraint("prefix_id", "cidr", name="uq_subnet_prefix_cidr"),
        Index("ix_subnets_bounds", "prefix_id", "network_int", "broadcast_int"),
        CheckConstraint("prefix_length BETWEEN 0 AND 32", name="ck_subnets_prefix_length"),
        CheckConstraint("vlan IS NULL OR vlan BETWEEN 1 AND 4094", name="ck_subnets_vlan"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prefix_id: Mapped[int] = mapped_column(ForeignKey("prefixes.id", ondelete="CASCADE"), nullable=False)
    parent_subnet_id: Mapped[int | None] = mapped_column(ForeignKey("subnets.id", ondelete="RESTRICT"))
    cidr: Mapped[str] = mapped_column(String(18), index=True, nullable=False)
    network_address: Mapped[str] = mapped_column(String(15), nullable=False)
    broadcast_address: Mapped[str] = mapped_column(String(15), nullable=False)
    prefix_length: Mapped[int] = mapped_column(Integer, nullable=False)
    first_usable_ip: Mapped[str] = mapped_column(String(15), nullable=False)
    last_usable_ip: Mapped[str] = mapped_column(String(15), nullable=False)
    network_int: Mapped[int] = mapped_column(BigInteger, nullable=False)
    broadcast_int: Mapped[int] = mapped_column(BigInteger, nullable=False)
    total_addresses: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[SubnetStatus] = mapped_column(
        Enum(
            SubnetStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="subnet_status",
        ),
        default=SubnetStatus.FREE,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text)
    vlan: Mapped[int | None] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    prefix = relationship("Prefix", back_populates="subnets")
    parent = relationship("Subnet", remote_side=[id], back_populates="children")
    children = relationship("Subnet", back_populates="parent")
    ip_addresses = relationship("IPAddress", back_populates="subnet")


class IPAddress(TimestampMixin, Base):
    __tablename__ = "ip_addresses"
    __table_args__ = (
        UniqueConstraint("prefix_id", "address", name="uq_ip_prefix_address"),
        Index("ix_ip_addresses_prefix_int", "prefix_id", "address_int"),
        Index("ix_ip_addresses_prefix_status_int", "prefix_id", "status", "address_int"),
        CheckConstraint("vlan IS NULL OR vlan BETWEEN 1 AND 4094", name="ck_ip_addresses_vlan"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    prefix_id: Mapped[int] = mapped_column(ForeignKey("prefixes.id", ondelete="CASCADE"), nullable=False)
    subnet_id: Mapped[int | None] = mapped_column(ForeignKey("subnets.id", ondelete="SET NULL"))
    address: Mapped[str] = mapped_column(String(15), index=True, nullable=False)
    address_int: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[IPStatus] = mapped_column(
        Enum(
            IPStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="ip_status",
        ),
        default=IPStatus.FREE,
        nullable=False,
    )
    reserved_by_subnet: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hostname: Mapped[str | None] = mapped_column(String(253), index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="RESTRICT"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id", ondelete="RESTRICT"))
    purpose: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    router_id: Mapped[int | None] = mapped_column(ForeignKey("routers.id", ondelete="RESTRICT"))
    interface: Mapped[str | None] = mapped_column(String(128))
    vlan: Mapped[int | None] = mapped_column(Integer)
    mac_address: Mapped[str | None] = mapped_column(String(17), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    reverse_dns: Mapped[str | None] = mapped_column(String(253))
    date_assigned: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    prefix = relationship("Prefix", back_populates="ip_addresses")
    subnet = relationship("Subnet", back_populates="ip_addresses")
    device = relationship("Device", back_populates="ip_addresses")
    customer = relationship("Customer", back_populates="ip_addresses")
    router = relationship("Router", back_populates="ip_addresses")
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])
    allocations = relationship("Allocation", back_populates="ip_address")


class Allocation(Base):
    __tablename__ = "allocations"
    __table_args__ = (Index("ix_allocations_ip_created", "ip_address_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ip_address_id: Mapped[int] = mapped_column(
        ForeignKey("ip_addresses.id", ondelete="RESTRICT"), nullable=False
    )
    subnet_id: Mapped[int | None] = mapped_column(ForeignKey("subnets.id", ondelete="SET NULL"))
    action: Mapped[AllocationAction] = mapped_column(
        Enum(
            AllocationAction,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="allocation_action",
        ),
        nullable=False,
    )
    previous_status: Mapped[IPStatus | None] = mapped_column(
        Enum(
            IPStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="allocation_previous_ip_status",
        )
    )
    new_status: Mapped[IPStatus] = mapped_column(
        Enum(
            IPStatus,
            values_callable=enum_values,
            native_enum=False,
            create_constraint=True,
            name="allocation_new_ip_status",
        ),
        nullable=False,
    )
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    ip_address = relationship("IPAddress", back_populates="allocations")
    subnet = relationship("Subnet")
    actor = relationship("User", back_populates="allocations")
