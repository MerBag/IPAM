from ipaddress import IPv4Network

from sqlalchemy import func, select

from app.enums import IPStatus
from app.models import IPAddress, Subnet
from app.services.ipam import create_prefix, network_values, split_preview, split_subnet


def test_ipv4_network_calculations():
    values = network_values(IPv4Network("203.0.113.0/24"))
    assert values["network_address"] == "203.0.113.0"
    assert values["broadcast_address"] == "203.0.113.255"
    assert values["first_usable_ip"] == "203.0.113.1"
    assert values["last_usable_ip"] == "203.0.113.254"
    assert values["total_addresses"] == 256

    point_to_point = network_values(IPv4Network("192.0.2.0/31"))
    assert point_to_point["first_usable_ip"] == "192.0.2.0"
    assert point_to_point["last_usable_ip"] == "192.0.2.1"


def test_prefix_materializes_every_address_and_boundaries(db, admin):
    prefix = create_prefix(
        db,
        cidr="203.0.113.0/29",
        description=None,
        location=None,
        actor=admin,
    )
    db.commit()
    assert db.scalar(select(func.count(IPAddress.id))) == 8
    first = db.scalar(select(IPAddress).where(IPAddress.address == "203.0.113.0"))
    last = db.scalar(select(IPAddress).where(IPAddress.address == "203.0.113.7"))
    assert first.status == IPStatus.NETWORK
    assert last.status == IPStatus.BROADCAST
    root = db.scalar(select(Subnet).where(Subnet.prefix_id == prefix.id))
    assert root.cidr == "203.0.113.0/29"


def test_split_preview_and_persistence_reclassifies_boundaries(db, admin):
    prefix = create_prefix(
        db,
        cidr="198.51.100.0/29",
        description=None,
        location=None,
        actor=admin,
    )
    db.flush()
    root = db.scalar(
        select(Subnet).where(Subnet.prefix_id == prefix.id, Subnet.parent_subnet_id.is_(None))
    )
    assert split_preview(root.cidr, 30) == ["198.51.100.0/30", "198.51.100.4/30"]
    _, children = split_subnet(db, subnet_id=root.id, new_prefix_length=30, actor=admin)
    db.commit()
    assert [item.cidr for item in children] == ["198.51.100.0/30", "198.51.100.4/30"]
    boundary = db.scalar(select(IPAddress).where(IPAddress.address == "198.51.100.3"))
    assert boundary.status == IPStatus.BROADCAST


def test_split_to_31_clears_inherited_parent_boundaries(db, admin):
    prefix = create_prefix(
        db,
        cidr="192.0.2.0/30",
        description=None,
        location=None,
        actor=admin,
    )
    db.flush()
    root = db.scalar(
        select(Subnet).where(Subnet.prefix_id == prefix.id, Subnet.parent_subnet_id.is_(None))
    )
    _, children = split_subnet(db, subnet_id=root.id, new_prefix_length=31, actor=admin)
    db.commit()
    assert [child.cidr for child in children] == ["192.0.2.0/31", "192.0.2.2/31"]
    statuses = list(
        db.scalars(select(IPAddress.status).order_by(IPAddress.address_int))
    )
    assert statuses == [IPStatus.FREE, IPStatus.FREE, IPStatus.FREE, IPStatus.FREE]
