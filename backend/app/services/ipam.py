from __future__ import annotations

from datetime import UTC, datetime
from ipaddress import IPv4Address, IPv4Network
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import Select, and_, func, or_, select, text, update
from sqlalchemy.orm import Session

from app.config import settings
from app.enums import AllocationAction, IPStatus, SubnetStatus
from app.models import Allocation, IPAddress, Prefix, Subnet, User


ACTIVE_IP_STATUSES = {
    IPStatus.ASSIGNED,
    IPStatus.RESERVED,
    IPStatus.GATEWAY,
    IPStatus.BLACKHOLED,
}


def independently_active_ip_clause():
    """Statuses representing explicit IP allocations, excluding subnet-managed holds."""
    return and_(
        IPAddress.status.in_(ACTIVE_IP_STATUSES),
        or_(
            IPAddress.status != IPStatus.RESERVED,
            IPAddress.reserved_by_subnet.is_(False),
        ),
    )


def network_values(network: IPv4Network) -> dict[str, int | str]:
    if network.prefixlen >= 31:
        first_usable = network.network_address
        last_usable = network.broadcast_address
    else:
        first_usable = IPv4Address(int(network.network_address) + 1)
        last_usable = IPv4Address(int(network.broadcast_address) - 1)
    return {
        "cidr": str(network),
        "network_address": str(network.network_address),
        "broadcast_address": str(network.broadcast_address),
        "prefix_length": network.prefixlen,
        "first_usable_ip": str(first_usable),
        "last_usable_ip": str(last_usable),
        "network_int": int(network.network_address),
        "broadcast_int": int(network.broadcast_address),
        "total_addresses": network.num_addresses,
    }


def default_status(network: IPv4Network, address: IPv4Address) -> IPStatus:
    if network.prefixlen <= 30 and address == network.network_address:
        return IPStatus.NETWORK
    if network.prefixlen <= 30 and address == network.broadcast_address:
        return IPStatus.BROADCAST
    return IPStatus.FREE


def ensure_materializable(network: IPv4Network) -> None:
    if network.num_addresses > settings.max_materialized_addresses:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Prefix contains {network.num_addresses} addresses; configured materialization "
                f"limit is {settings.max_materialized_addresses}"
            ),
        )


def create_prefix(
    db: Session,
    *,
    cidr: str,
    description: str | None,
    location: str | None,
    actor: User | None,
) -> Prefix:
    network = IPv4Network(cidr, strict=True)
    ensure_materializable(network)
    # Serialize overlap checks; an exact unique key alone cannot prevent two different,
    # concurrently inserted CIDRs from overlapping.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(721149205)"))
    lower, upper = int(network.network_address), int(network.broadcast_address)
    overlap = db.scalar(
        select(Prefix.id).where(
            and_(Prefix.network_int <= upper, Prefix.broadcast_int >= lower)
        ).limit(1)
    )
    if overlap is not None:
        raise HTTPException(status_code=409, detail="Prefix overlaps an existing prefix")

    prefix = Prefix(
        **network_values(network),
        description=description,
        location=location,
        created_by_id=actor.id if actor else None,
    )
    db.add(prefix)
    db.flush()
    root = Subnet(
        prefix_id=prefix.id,
        **network_values(network),
        status=SubnetStatus.FREE,
        description="Root subnet",
        location=location,
        created_by_id=actor.id if actor else None,
    )
    db.add(root)
    db.flush()

    batch: list[IPAddress] = []
    for address in network:
        batch.append(
            IPAddress(
                prefix_id=prefix.id,
                subnet_id=root.id,
                address=str(address),
                address_int=int(address),
                status=default_status(network, address),
            )
        )
        if len(batch) >= 2048:
            db.add_all(batch)
            db.flush()
            batch.clear()
    if batch:
        db.add_all(batch)
    db.flush()
    return prefix


def prefix_with_stats(db: Session, prefix: Prefix) -> dict:
    counts = dict(
        db.execute(
            select(IPAddress.status, func.count(IPAddress.id))
            .where(IPAddress.prefix_id == prefix.id)
            .group_by(IPAddress.status)
        ).all()
    )
    free = int(counts.get(IPStatus.FREE, 0))
    used = int(prefix.total_addresses - free)
    data = {column.name: getattr(prefix, column.name) for column in Prefix.__table__.columns}
    data.update(
        used_addresses=used,
        free_addresses=free,
        utilization_percent=round((used / prefix.total_addresses) * 100, 2)
        if prefix.total_addresses
        else 0,
    )
    return data


def subnets_with_stats(db: Session, subnets: Iterable[Subnet]) -> list[dict]:
    """Return subnet DTOs with address counts calculated over each CIDR range.

    Range joins intentionally ignore ``ip_addresses.subnet_id`` so container subnet
    totals include every descendant assignment.
    """
    subnet_list = list(subnets)
    if not subnet_list:
        return []
    ids = [subnet.id for subnet in subnet_list]
    rows = db.execute(
        select(Subnet.id, IPAddress.status, func.count(IPAddress.id))
        .join(
            IPAddress,
            and_(
                IPAddress.prefix_id == Subnet.prefix_id,
                IPAddress.address_int >= Subnet.network_int,
                IPAddress.address_int <= Subnet.broadcast_int,
            ),
        )
        .where(Subnet.id.in_(ids))
        .group_by(Subnet.id, IPAddress.status)
    ).all()
    counts: dict[int, dict[IPStatus, int]] = {}
    for subnet_id, ip_status, count in rows:
        counts.setdefault(subnet_id, {})[ip_status] = int(count)
    results: list[dict] = []
    for subnet in subnet_list:
        free = counts.get(subnet.id, {}).get(IPStatus.FREE, 0)
        used = int(subnet.total_addresses - free)
        data = {column.name: getattr(subnet, column.name) for column in Subnet.__table__.columns}
        data.update(
            used_addresses=used,
            free_addresses=free,
            utilization_percent=round((used / subnet.total_addresses) * 100, 2)
            if subnet.total_addresses
            else 0,
        )
        results.append(data)
    return results


def subnet_with_stats(db: Session, subnet: Subnet) -> dict:
    return subnets_with_stats(db, [subnet])[0]


def split_preview(cidr: str, new_prefix_length: int) -> list[str]:
    parent = IPv4Network(cidr)
    if new_prefix_length <= parent.prefixlen:
        raise HTTPException(status_code=422, detail="New prefix length must be larger than the parent")
    count = 1 << (new_prefix_length - parent.prefixlen)
    if count > 4096:
        raise HTTPException(status_code=422, detail="Split would create more than 4096 subnets")
    return [str(network) for network in parent.subnets(new_prefix=new_prefix_length)]


def _assert_boundary_ips_available(db: Session, networks: Iterable[IPv4Network]) -> None:
    boundary_ints: set[int] = set()
    for network in networks:
        if network.prefixlen <= 30:
            boundary_ints.update((int(network.network_address), int(network.broadcast_address)))
    if not boundary_ints:
        return
    conflict = db.scalar(
        select(IPAddress.address)
        .where(
            IPAddress.address_int.in_(boundary_ints),
            independently_active_ip_clause(),
        )
        .limit(1)
    )
    if conflict:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot create subnet boundary because {conflict} is in use",
        )


def _apply_subnet_to_ips(db: Session, subnet: Subnet, network: IPv4Network) -> None:
    db.execute(
        update(IPAddress)
        .where(
            IPAddress.prefix_id == subnet.prefix_id,
            IPAddress.address_int.between(subnet.network_int, subnet.broadcast_int),
        )
        .values(subnet_id=subnet.id)
    )
    db.execute(
        update(IPAddress)
        .where(
            IPAddress.prefix_id == subnet.prefix_id,
            IPAddress.address_int.between(subnet.network_int, subnet.broadcast_int),
            IPAddress.reserved_by_subnet.is_(True),
        )
        .values(status=IPStatus.FREE, reserved_by_subnet=False)
    )
    # Parent /30 boundaries become usable when the new child is /31 or /32.
    # Clear only system-managed markers; active allocations are guarded earlier.
    db.execute(
        update(IPAddress)
        .where(
            IPAddress.prefix_id == subnet.prefix_id,
            IPAddress.address_int.between(subnet.network_int, subnet.broadcast_int),
            IPAddress.status.in_([IPStatus.NETWORK, IPStatus.BROADCAST]),
        )
        .values(status=IPStatus.FREE, reserved_by_subnet=False)
    )
    if network.prefixlen <= 30:
        db.execute(
            update(IPAddress)
            .where(
                IPAddress.prefix_id == subnet.prefix_id,
                IPAddress.address_int == subnet.network_int,
            )
            .values(status=IPStatus.NETWORK, reserved_by_subnet=False)
        )
        db.execute(
            update(IPAddress)
            .where(
                IPAddress.prefix_id == subnet.prefix_id,
                IPAddress.address_int == subnet.broadcast_int,
            )
            .values(status=IPStatus.BROADCAST, reserved_by_subnet=False)
        )
    if subnet.status == SubnetStatus.RESERVED:
        db.execute(
            update(IPAddress)
            .where(
                IPAddress.prefix_id == subnet.prefix_id,
                IPAddress.address_int.between(subnet.network_int, subnet.broadcast_int),
                IPAddress.status == IPStatus.FREE,
            )
            .values(status=IPStatus.RESERVED, reserved_by_subnet=True)
        )


def sync_subnet_reservation(
    db: Session, *, subnet: Subnet, previous_status: SubnetStatus
) -> None:
    if previous_status == SubnetStatus.RESERVED and subnet.status != SubnetStatus.RESERVED:
        db.execute(
            update(IPAddress)
            .where(
                IPAddress.prefix_id == subnet.prefix_id,
                IPAddress.address_int.between(subnet.network_int, subnet.broadcast_int),
                IPAddress.reserved_by_subnet.is_(True),
            )
            .values(status=IPStatus.FREE, reserved_by_subnet=False)
        )
    elif previous_status != SubnetStatus.RESERVED and subnet.status == SubnetStatus.RESERVED:
        db.execute(
            update(IPAddress)
            .where(
                IPAddress.prefix_id == subnet.prefix_id,
                IPAddress.address_int.between(subnet.network_int, subnet.broadcast_int),
                IPAddress.status == IPStatus.FREE,
            )
            .values(status=IPStatus.RESERVED, reserved_by_subnet=True)
        )


def split_subnet(
    db: Session, *, subnet_id: int, new_prefix_length: int, actor: User
) -> tuple[Subnet, list[Subnet]]:
    prefix_id = db.scalar(select(Subnet.prefix_id).where(Subnet.id == subnet_id))
    if prefix_id is None:
        raise HTTPException(status_code=404, detail="Subnet not found")
    db.scalar(select(Prefix.id).where(Prefix.id == prefix_id).with_for_update())
    parent = db.scalar(select(Subnet).where(Subnet.id == subnet_id).with_for_update())
    if parent is None:
        raise HTTPException(status_code=404, detail="Subnet not found")
    if db.scalar(select(Subnet.id).where(Subnet.parent_subnet_id == parent.id).limit(1)):
        raise HTTPException(status_code=409, detail="Subnet has already been split")
    networks = [IPv4Network(cidr) for cidr in split_preview(parent.cidr, new_prefix_length)]
    _assert_boundary_ips_available(db, networks)
    active_address_ints = set(
        db.scalars(
            select(IPAddress.address_int).where(
                IPAddress.prefix_id == parent.prefix_id,
                IPAddress.address_int.between(parent.network_int, parent.broadcast_int),
                independently_active_ip_clause(),
            )
        )
    )
    children: list[Subnet] = []
    for network in networks:
        child_has_allocations = any(
            int(network.network_address) <= value <= int(network.broadcast_address)
            for value in active_address_ints
        )
        child_status = (
            parent.status
            if parent.parent_subnet_id is not None
            and parent.status in {SubnetStatus.ALLOCATED, SubnetStatus.RESERVED}
            else SubnetStatus.ALLOCATED if child_has_allocations else SubnetStatus.FREE
        )
        child = Subnet(
            prefix_id=parent.prefix_id,
            parent_subnet_id=parent.id,
            **network_values(network),
            status=child_status,
            location=parent.location,
            created_by_id=actor.id,
        )
        db.add(child)
        db.flush()
        _apply_subnet_to_ips(db, child, network)
        children.append(child)
    parent.status = SubnetStatus.CONTAINER
    db.flush()
    return parent, children


def create_child_subnet(
    db: Session,
    *,
    prefix: Prefix,
    parent: Subnet,
    network: IPv4Network,
    status: SubnetStatus,
    description: str | None,
    vlan: int | None,
    location: str | None,
    actor: User,
) -> Subnet:
    db.scalar(select(Prefix.id).where(Prefix.id == prefix.id).with_for_update())
    parent = db.scalar(select(Subnet).where(Subnet.id == parent.id).with_for_update())
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent subnet not found")
    if not network.subnet_of(IPv4Network(parent.cidr)) or network == IPv4Network(parent.cidr):
        raise HTTPException(status_code=422, detail="Subnet must be a proper child of its parent")
    sibling_overlap = db.scalar(
        select(Subnet.id)
        .where(
            Subnet.parent_subnet_id == parent.id,
            Subnet.network_int <= int(network.broadcast_address),
            Subnet.broadcast_int >= int(network.network_address),
        )
        .limit(1)
    )
    if sibling_overlap:
        raise HTTPException(status_code=409, detail="Subnet overlaps an existing child subnet")
    if status in {SubnetStatus.FREE, SubnetStatus.RESERVED}:
        active = db.scalar(
            select(IPAddress.address)
            .where(
                IPAddress.prefix_id == prefix.id,
                IPAddress.address_int.between(
                    int(network.network_address), int(network.broadcast_address)
                ),
                independently_active_ip_clause(),
            )
            .limit(1)
        )
        if active:
            raise HTTPException(
                status_code=409,
                detail=f"Subnet would contain active address {active}",
            )
    _assert_boundary_ips_available(db, [network])
    subnet = Subnet(
        prefix_id=prefix.id,
        parent_subnet_id=parent.id,
        **network_values(network),
        status=status,
        description=description,
        vlan=vlan,
        location=location,
        created_by_id=actor.id,
    )
    db.add(subnet)
    db.flush()
    _apply_subnet_to_ips(db, subnet, network)
    parent.status = SubnetStatus.CONTAINER
    db.flush()
    return subnet


ASSIGNMENT_FIELD_NAMES = (
    "hostname",
    "device_id",
    "customer_id",
    "purpose",
    "location",
    "router_id",
    "interface",
    "vlan",
    "mac_address",
    "notes",
    "reverse_dns",
)


def ip_snapshot(ip: IPAddress) -> dict:
    return {
        "address": ip.address,
        "status": ip.status.value,
        **{name: getattr(ip, name) for name in ASSIGNMENT_FIELD_NAMES},
        "date_assigned": ip.date_assigned.isoformat() if ip.date_assigned else None,
        "assigned_by_id": ip.assigned_by_id,
    }


def record_allocation(
    db: Session,
    *,
    ip: IPAddress,
    action: AllocationAction,
    previous_status: IPStatus | None,
    actor: User,
    snapshot: dict | None = None,
) -> Allocation:
    allocation = Allocation(
        ip_address_id=ip.id,
        subnet_id=ip.subnet_id,
        action=action,
        previous_status=previous_status,
        new_status=ip.status,
        snapshot=snapshot or ip_snapshot(ip),
        actor_id=actor.id,
        created_at=datetime.now(UTC),
    )
    db.add(allocation)
    return allocation


def lock_ip(db: Session, ip_id: int) -> IPAddress:
    location = db.execute(
        select(IPAddress.prefix_id, IPAddress.subnet_id).where(IPAddress.id == ip_id)
    ).one_or_none()
    if location is None:
        raise HTTPException(status_code=404, detail="IP address not found")
    prefix_id, subnet_id = location
    db.scalar(select(Prefix.id).where(Prefix.id == prefix_id).with_for_update())
    if subnet_id is not None:
        db.scalar(select(Subnet.id).where(Subnet.id == subnet_id).with_for_update())
    ip = db.scalar(select(IPAddress).where(IPAddress.id == ip_id).with_for_update())
    if ip is None:
        raise HTTPException(status_code=404, detail="IP address not found")
    return ip


def validate_foreign_references(db: Session, fields: dict) -> None:
    from app.models import Customer, Device, Router

    references = (("device_id", Device), ("customer_id", Customer), ("router_id", Router))
    for name, model in references:
        value = fields.get(name)
        if value is not None:
            query = select(model).where(model.id == value)
            if db.bind is not None and db.bind.dialect.name == "postgresql":
                query = query.with_for_update(read=True, key_share=True)
            if db.scalar(query) is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"{name} does not reference an existing record",
                )


def assign_ip(
    db: Session,
    *,
    ip: IPAddress,
    fields: dict,
    status: IPStatus,
    actor: User,
    action: AllocationAction = AllocationAction.ASSIGNED,
) -> IPAddress:
    if ip.status != IPStatus.FREE:
        raise HTTPException(status_code=409, detail=f"IP address is {ip.status.value}, not free")
    subnet = db.get(Subnet, ip.subnet_id) if ip.subnet_id is not None else None
    if subnet is not None and subnet.status == SubnetStatus.RESERVED:
        raise HTTPException(status_code=409, detail="IP address belongs to a reserved subnet")
    validate_foreign_references(db, fields)
    previous = ip.status
    for name in ASSIGNMENT_FIELD_NAMES:
        if name in fields:
            setattr(ip, name, fields[name])
    ip.status = status
    ip.date_assigned = datetime.now(UTC)
    ip.assigned_by_id = actor.id
    if ip.subnet_id is not None:
        if (
            subnet is not None
            and subnet.parent_subnet_id is not None
            and subnet.status == SubnetStatus.FREE
        ):
            subnet.status = SubnetStatus.ALLOCATED
    record_allocation(db, ip=ip, action=action, previous_status=previous, actor=actor)
    db.flush()
    return ip


def edit_ip(db: Session, *, ip: IPAddress, fields: dict, actor: User) -> IPAddress:
    if ip.status in {IPStatus.NETWORK, IPStatus.BROADCAST, IPStatus.FREE}:
        raise HTTPException(status_code=409, detail=f"Cannot edit an IP in {ip.status.value} state")
    if ip.reserved_by_subnet:
        raise HTTPException(status_code=409, detail="Subnet-managed reservations cannot be edited")
    fields = fields.copy()
    validate_foreign_references(db, fields)
    before = ip_snapshot(ip)
    previous = ip.status
    new_status = fields.pop("status", None)
    for name in ASSIGNMENT_FIELD_NAMES:
        if name in fields:
            setattr(ip, name, fields[name])
    if new_status is not None:
        ip.status = new_status
    record_allocation(
        db,
        ip=ip,
        action=AllocationAction.MODIFIED,
        previous_status=previous,
        actor=actor,
        snapshot={"before": before, "after": ip_snapshot(ip)},
    )
    db.flush()
    return ip


def release_ip(db: Session, *, ip: IPAddress, actor: User) -> IPAddress:
    if ip.status not in ACTIVE_IP_STATUSES:
        raise HTTPException(status_code=409, detail=f"Cannot release an IP in {ip.status.value} state")
    if ip.reserved_by_subnet:
        raise HTTPException(status_code=409, detail="Subnet-managed reservations cannot be released")
    before = ip_snapshot(ip)
    previous = ip.status
    ip.status = IPStatus.FREE
    for name in ASSIGNMENT_FIELD_NAMES:
        setattr(ip, name, None)
    ip.date_assigned = None
    ip.assigned_by_id = None
    ip.reserved_by_subnet = False
    record_allocation(
        db,
        ip=ip,
        action=AllocationAction.RELEASED,
        previous_status=previous,
        actor=actor,
        snapshot=before,
    )
    db.flush()
    return ip


def next_free_ip_query(*, prefix_id: int, subnet_id: int | None = None) -> Select:
    query = (
        select(IPAddress)
        .join(Subnet, IPAddress.subnet_id == Subnet.id)
        .where(
            IPAddress.prefix_id == prefix_id,
            IPAddress.status == IPStatus.FREE,
            Subnet.status != SubnetStatus.RESERVED,
        )
    )
    if subnet_id is not None:
        query = query.where(IPAddress.subnet_id == subnet_id)
    return query.order_by(IPAddress.address_int).limit(1)
