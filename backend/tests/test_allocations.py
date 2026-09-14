from sqlalchemy import select

from app.enums import AllocationAction, IPStatus, UserRole
from app.models import Allocation, IPAddress, User
from app.security import hash_password
from app.services.ipam import assign_ip, create_prefix, edit_ip, release_ip


def test_release_keeps_permanent_allocation_history(db, admin):
    prefix = create_prefix(
        db,
        cidr="203.0.113.0/29",
        description=None,
        location=None,
        actor=admin,
    )
    db.flush()
    ip = db.scalar(
        select(IPAddress)
        .where(IPAddress.prefix_id == prefix.id, IPAddress.status == IPStatus.FREE)
        .order_by(IPAddress.address_int)
    )
    assign_ip(
        db,
        ip=ip,
        fields={"hostname": "edge-01", "purpose": "Transit"},
        status=IPStatus.ASSIGNED,
        actor=admin,
    )
    release_ip(db, ip=ip, actor=admin)
    db.commit()

    history = list(
        db.scalars(select(Allocation).where(Allocation.ip_address_id == ip.id).order_by(Allocation.id))
    )
    assert [entry.action for entry in history] == [
        AllocationAction.ASSIGNED,
        AllocationAction.RELEASED,
    ]
    assert history[-1].snapshot["hostname"] == "edge-01"
    assert ip.status == IPStatus.FREE
    assert ip.hostname is None


def test_edit_schema_cannot_bypass_release_cleanup():
    from pydantic import ValidationError
    from app.schemas.ipam import EditIPRequest

    try:
        EditIPRequest(status=IPStatus.FREE)
    except ValidationError as exc:
        assert "system-managed" in str(exc)
    else:
        raise AssertionError("free status must be rejected")


def test_metadata_edit_preserves_original_assigner(db, admin):
    operator = User(
        username="operator",
        password_hash=hash_password("operator-password-long-enough"),
        role=UserRole.OPERATOR,
        is_active=True,
    )
    db.add(operator)
    prefix = create_prefix(
        db,
        cidr="203.0.113.48/29",
        description=None,
        location=None,
        actor=admin,
    )
    db.flush()
    ip = db.scalar(
        select(IPAddress)
        .where(IPAddress.prefix_id == prefix.id, IPAddress.status == IPStatus.FREE)
        .order_by(IPAddress.address_int)
    )
    assign_ip(
        db,
        ip=ip,
        fields={"hostname": "original"},
        status=IPStatus.ASSIGNED,
        actor=admin,
    )
    edit_ip(db, ip=ip, fields={"hostname": "renamed"}, actor=operator)
    db.commit()
    assert ip.assigned_by_id == admin.id
    latest = db.scalar(
        select(Allocation)
        .where(Allocation.ip_address_id == ip.id)
        .order_by(Allocation.id.desc())
    )
    assert latest.actor_id == operator.id
