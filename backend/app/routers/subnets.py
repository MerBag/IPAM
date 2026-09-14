from bisect import bisect_left, bisect_right
from ipaddress import IPv4Network

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import exists, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import admin_required, get_current_user, operator_required
from app.enums import AuditAction, IPStatus, SubnetStatus
from app.models import IPAddress, Prefix, Subnet, User
from app.schemas.ipam import (
    NextSubnetPreview,
    NextSubnetRequest,
    SplitPreview,
    SplitRequest,
    SubnetCreate,
    SubnetRead,
    SubnetUpdate,
)
from app.services.audit import write_audit
from app.services.ipam import (
    ACTIVE_IP_STATUSES,
    create_child_subnet,
    independently_active_ip_clause,
    subnet_with_stats,
    split_preview,
    split_subnet,
    subnets_with_stats,
    sync_subnet_reservation,
)


router = APIRouter(prefix="/subnets", tags=["Subnets"], dependencies=[Depends(get_current_user)])


def _merged_intervals(intervals: list[tuple[int, int]]) -> tuple[list[int], list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [item[0] for item in merged], [item[1] for item in merged]


def _range_overlaps(starts: list[int], ends: list[int], start: int, end: int) -> bool:
    index = bisect_right(starts, end) - 1
    return index >= 0 and ends[index] >= start


def _next_candidate(
    db: Session, prefix: Prefix, prefix_length: int
) -> tuple[str, Subnet | None, Subnet | None]:
    if prefix_length <= prefix.prefix_length:
        raise HTTPException(status_code=422, detail="Requested subnet must be smaller than the prefix")
    has_active_ip = exists(
        select(IPAddress.id).where(
            IPAddress.prefix_id == Subnet.prefix_id,
            IPAddress.address_int >= Subnet.network_int,
            IPAddress.address_int <= Subnet.broadcast_int,
            IPAddress.status.in_(ACTIVE_IP_STATUSES),
        )
    )
    exact_subnets = list(
        db.scalars(
            select(Subnet)
            .where(
                Subnet.prefix_id == prefix.id,
                Subnet.prefix_length == prefix_length,
                Subnet.status == SubnetStatus.FREE,
                ~has_active_ip,
            )
            .order_by(Subnet.network_int)
        )
    )
    root = IPv4Network(prefix.cidr)
    all_subnets = list(
        db.scalars(
            select(Subnet)
            .where(Subnet.prefix_id == prefix.id)
            .order_by(Subnet.network_int, Subnet.prefix_length.desc())
        )
    )
    active_addresses = sorted(
        db.scalars(
            select(IPAddress.address_int).where(
                IPAddress.prefix_id == prefix.id,
                IPAddress.status.in_(ACTIVE_IP_STATUSES),
            )
        )
    )
    candidate_count = 1 << (prefix_length - root.prefixlen)
    if candidate_count > 65536:
        raise HTTPException(status_code=422, detail="Search space is too large")
    options: list[tuple[int, str, Subnet | None, Subnet | None]] = [
        (subnet.network_int, subnet.cidr, subnet, None) for subnet in exact_subnets
    ]
    eligible_parents = [
        subnet
        for subnet in all_subnets
        if subnet.prefix_length < prefix_length
        and subnet.status in {SubnetStatus.FREE, SubnetStatus.CONTAINER}
    ]
    for parent in eligible_parents:
        descendant_intervals = [
            (subnet.network_int, subnet.broadcast_int)
            for subnet in all_subnets
            if subnet.id != parent.id
            and subnet.network_int >= parent.network_int
            and subnet.broadcast_int <= parent.broadcast_int
        ]
        starts, ends = _merged_intervals(descendant_intervals)
        for candidate in IPv4Network(parent.cidr).subnets(new_prefix=prefix_length):
            candidate_start = int(candidate.network_address)
            candidate_end = int(candidate.broadcast_address)
            active_index = bisect_left(active_addresses, candidate_start)
            contains_active_ip = (
                active_index < len(active_addresses) and active_addresses[active_index] <= candidate_end
            )
            if not contains_active_ip and not _range_overlaps(
                starts, ends, candidate_start, candidate_end
            ):
                options.append((candidate_start, str(candidate), None, parent))
                break
    if options:
        _, cidr, existing, parent = min(
            options,
            key=lambda item: (
                item[0],
                0 if item[2] is not None else -(item[3].prefix_length if item[3] else 0),
            ),
        )
        return cidr, existing, parent
    raise HTTPException(status_code=404, detail="No available subnet of the requested size")


@router.get("", response_model=list[SubnetRead])
def list_subnets(
    prefix_id: int | None = None,
    parent_subnet_id: int | None = None,
    leaf_only: bool = False,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    query = select(Subnet)
    if prefix_id is not None:
        query = query.where(Subnet.prefix_id == prefix_id)
    if parent_subnet_id is not None:
        query = query.where(Subnet.parent_subnet_id == parent_subnet_id)
    if leaf_only:
        child = select(Subnet.parent_subnet_id).where(Subnet.parent_subnet_id.is_not(None))
        query = query.where(Subnet.id.not_in(child))
    subnets = list(
        db.scalars(query.order_by(Subnet.network_int, Subnet.prefix_length).offset(skip).limit(limit))
    )
    return subnets_with_stats(db, subnets)


@router.get("/next-available", response_model=NextSubnetPreview)
def next_available_subnet(
    prefix_id: int,
    prefix_length: int = Query(ge=1, le=32),
    db: Session = Depends(get_db),
):
    prefix = db.get(Prefix, prefix_id)
    if prefix is None:
        raise HTTPException(status_code=404, detail="Prefix not found")
    cidr, existing, parent = _next_candidate(db, prefix, prefix_length)
    return NextSubnetPreview(
        cidr=cidr,
        subnet_id=existing.id if existing else None,
        parent_subnet_id=existing.parent_subnet_id if existing else parent.id if parent else None,
        already_materialized=existing is not None,
    )


@router.post("/next-available/allocate", response_model=SubnetRead, status_code=201)
def allocate_next_subnet(
    payload: NextSubnetRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    prefix = db.scalar(select(Prefix).where(Prefix.id == payload.prefix_id).with_for_update())
    if prefix is None:
        raise HTTPException(status_code=404, detail="Prefix not found")
    cidr, existing, parent = _next_candidate(db, prefix, payload.prefix_length)
    was_materialized = existing is not None
    if existing:
        subnet = db.scalar(
            select(Subnet).where(Subnet.id == existing.id).with_for_update()
        )
        previous_status = subnet.status
        subnet.status = payload.status
        subnet.description = payload.description
        subnet.vlan = payload.vlan
        subnet.location = payload.location
        sync_subnet_reservation(db, subnet=subnet, previous_status=previous_status)
    else:
        if parent is None:
            raise HTTPException(status_code=409, detail="Eligible parent subnet is missing")
        subnet = create_child_subnet(
            db,
            prefix=prefix,
            parent=parent,
            network=IPv4Network(cidr),
            status=payload.status,
            description=payload.description,
            vlan=payload.vlan,
            location=payload.location,
            actor=actor,
        )
    write_audit(
        db,
        action=AuditAction.SUBNET_MODIFIED if was_materialized else AuditAction.SUBNET_CREATED,
        actor=actor,
        entity_type="subnet",
        entity_id=subnet.id,
        details={"cidr": subnet.cidr, "allocation": "next_available", "status": subnet.status.value},
        request=request,
    )
    db.commit()
    db.refresh(subnet)
    return subnet_with_stats(db, subnet)


@router.post("", response_model=SubnetRead, status_code=201)
def create_subnet(
    payload: SubnetCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    prefix = db.scalar(select(Prefix).where(Prefix.id == payload.prefix_id).with_for_update())
    if prefix is None:
        raise HTTPException(status_code=404, detail="Prefix not found")
    network = IPv4Network(payload.cidr)
    if not network.subnet_of(IPv4Network(prefix.cidr)):
        raise HTTPException(status_code=422, detail="Subnet is outside the selected prefix")
    if payload.parent_subnet_id:
        parent = db.get(Subnet, payload.parent_subnet_id)
        if parent is None or parent.prefix_id != prefix.id:
            raise HTTPException(status_code=422, detail="Parent subnet is invalid")
    else:
        parent = db.scalar(
            select(Subnet)
            .where(
                Subnet.prefix_id == prefix.id,
                Subnet.network_int <= int(network.network_address),
                Subnet.broadcast_int >= int(network.broadcast_address),
                Subnet.prefix_length < network.prefixlen,
            )
            .order_by(Subnet.prefix_length.desc())
            .limit(1)
        )
        if parent is None:
            raise HTTPException(
                status_code=409,
                detail="No eligible containing parent subnet is available",
            )
    if parent.status not in {SubnetStatus.FREE, SubnetStatus.CONTAINER}:
        raise HTTPException(
            status_code=409,
            detail="No eligible containing parent subnet is available for subdivision",
        )
    try:
        subnet = create_child_subnet(
            db,
            prefix=prefix,
            parent=parent,
            network=network,
            status=payload.status,
            description=payload.description,
            vlan=payload.vlan,
            location=payload.location,
            actor=actor,
        )
        write_audit(
            db,
            action=AuditAction.SUBNET_CREATED,
            actor=actor,
            entity_type="subnet",
            entity_id=subnet.id,
            details={"cidr": subnet.cidr, "parent_id": parent.id},
            request=request,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Subnet already exists")
    db.refresh(subnet)
    return subnet_with_stats(db, subnet)


@router.get("/{subnet_id}", response_model=SubnetRead)
def get_subnet(subnet_id: int, db: Session = Depends(get_db)):
    subnet = db.get(Subnet, subnet_id)
    if subnet is None:
        raise HTTPException(status_code=404, detail="Subnet not found")
    return subnet_with_stats(db, subnet)


@router.patch("/{subnet_id}", response_model=SubnetRead)
def update_subnet(
    subnet_id: int,
    payload: SubnetUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    prefix_id = db.scalar(select(Subnet.prefix_id).where(Subnet.id == subnet_id))
    if prefix_id is None:
        raise HTTPException(status_code=404, detail="Subnet not found")
    db.scalar(select(Prefix.id).where(Prefix.id == prefix_id).with_for_update())
    subnet = db.scalar(select(Subnet).where(Subnet.id == subnet_id).with_for_update())
    if subnet is None:
        raise HTTPException(status_code=404, detail="Subnet not found")
    if subnet.parent_subnet_id is None and payload.status not in (None, SubnetStatus.CONTAINER):
        raise HTTPException(status_code=409, detail="Root subnet status is system-managed")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one field must be supplied")
    has_children = db.scalar(
        select(Subnet.id).where(Subnet.parent_subnet_id == subnet.id).limit(1)
    )
    if "status" in changes and has_children and changes["status"] != SubnetStatus.CONTAINER:
        raise HTTPException(status_code=409, detail="A subnet with children must remain a container")
    target_status = changes.get("status")
    if target_status in {SubnetStatus.FREE, SubnetStatus.RESERVED}:
        active = db.scalar(
            select(IPAddress.address)
            .where(
                IPAddress.prefix_id == subnet.prefix_id,
                IPAddress.address_int.between(subnet.network_int, subnet.broadcast_int),
                independently_active_ip_clause(),
            )
            .limit(1)
        )
        if active:
            raise HTTPException(status_code=409, detail=f"Subnet contains active address {active}")
        if target_status == SubnetStatus.FREE and has_children:
            raise HTTPException(status_code=409, detail="Container subnet cannot be marked free")
    if target_status == SubnetStatus.CONTAINER and not has_children:
        raise HTTPException(status_code=409, detail="A leaf subnet cannot be marked as a container")
    previous_status = subnet.status
    for key, value in changes.items():
        setattr(subnet, key, value)
    sync_subnet_reservation(db, subnet=subnet, previous_status=previous_status)
    write_audit(
        db,
        action=AuditAction.SUBNET_MODIFIED,
        actor=actor,
        entity_type="subnet",
        entity_id=subnet.id,
        details={"cidr": subnet.cidr, "changed_fields": sorted(changes)},
        request=request,
    )
    db.commit()
    db.refresh(subnet)
    return subnet_with_stats(db, subnet)


@router.get("/{subnet_id}/split-preview", response_model=SplitPreview)
def preview_subnet_split(
    subnet_id: int,
    new_prefix_length: int = Query(ge=1, le=32),
    db: Session = Depends(get_db),
):
    subnet = db.get(Subnet, subnet_id)
    if subnet is None:
        raise HTTPException(status_code=404, detail="Subnet not found")
    cidrs = split_preview(subnet.cidr, new_prefix_length)
    return SplitPreview(
        parent_cidr=subnet.cidr,
        new_prefix_length=new_prefix_length,
        count=len(cidrs),
        subnets=cidrs,
    )


@router.post("/{subnet_id}/split", response_model=list[SubnetRead], status_code=201)
def persist_subnet_split(
    subnet_id: int,
    payload: SplitRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    parent, children = split_subnet(
        db,
        subnet_id=subnet_id,
        new_prefix_length=payload.new_prefix_length,
        actor=actor,
    )
    for child in children:
        write_audit(
            db,
            action=AuditAction.SUBNET_CREATED,
            actor=actor,
            entity_type="subnet",
            entity_id=child.id,
            details={"cidr": child.cidr, "parent_id": parent.id},
            request=request,
        )
    db.commit()
    return subnets_with_stats(db, children)


@router.delete("/{subnet_id}", status_code=204)
def delete_subnet(
    subnet_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin_required),
):
    prefix_id = db.scalar(select(Subnet.prefix_id).where(Subnet.id == subnet_id))
    if prefix_id is None:
        raise HTTPException(status_code=404, detail="Subnet not found")
    db.scalar(select(Prefix.id).where(Prefix.id == prefix_id).with_for_update())
    subnet = db.scalar(select(Subnet).where(Subnet.id == subnet_id).with_for_update())
    if subnet is None:
        raise HTTPException(status_code=404, detail="Subnet not found")
    if subnet.parent_subnet_id is None:
        raise HTTPException(status_code=409, detail="Root subnet cannot be deleted independently")
    if db.scalar(select(Subnet.id).where(Subnet.parent_subnet_id == subnet.id).limit(1)):
        raise HTTPException(status_code=409, detail="Delete child subnets first")
    active = db.scalar(
        select(IPAddress.address)
        .where(
            IPAddress.subnet_id == subnet.id,
            independently_active_ip_clause(),
        )
        .limit(1)
    )
    if active:
        raise HTTPException(status_code=409, detail=f"Subnet contains active address {active}")
    parent = db.get(Subnet, subnet.parent_subnet_id)
    db.execute(
        update(IPAddress)
        .where(IPAddress.subnet_id == subnet.id)
        .values(subnet_id=parent.id, status=IPStatus.FREE, reserved_by_subnet=False)
    )
    parent_network = IPv4Network(parent.cidr)
    if parent_network.prefixlen <= 30:
        db.execute(
            update(IPAddress)
            .where(
                IPAddress.prefix_id == parent.prefix_id,
                IPAddress.address_int == parent.network_int,
            )
            .values(status=IPStatus.NETWORK)
        )
        db.execute(
            update(IPAddress)
            .where(
                IPAddress.prefix_id == parent.prefix_id,
                IPAddress.address_int == parent.broadcast_int,
            )
            .values(status=IPStatus.BROADCAST)
        )
    details = {"cidr": subnet.cidr, "parent_id": parent.id}
    db.delete(subnet)
    db.flush()
    if not db.scalar(select(Subnet.id).where(Subnet.parent_subnet_id == parent.id).limit(1)):
        parent_has_active_ip = db.scalar(
            select(IPAddress.id)
            .where(
                IPAddress.prefix_id == parent.prefix_id,
                IPAddress.address_int.between(parent.network_int, parent.broadcast_int),
                independently_active_ip_clause(),
            )
            .limit(1)
        )
        parent.status = (
            SubnetStatus.ALLOCATED if parent_has_active_ip else SubnetStatus.FREE
        )
    write_audit(
        db,
        action=AuditAction.SUBNET_DELETED,
        actor=actor,
        entity_type="subnet",
        entity_id=subnet_id,
        details=details,
        request=request,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
