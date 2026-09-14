from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, operator_required
from app.enums import AllocationAction, AuditAction, IPStatus
from app.models import Allocation, Customer, Device, IPAddress, Prefix, Router, Subnet, User
from app.schemas.ipam import (
    AllocationRead,
    AssignIPRequest,
    EditIPRequest,
    IPAddressRead,
    NextIPAssignmentRequest,
    ReserveIPRequest,
)
from app.services.audit import write_audit
from app.services.ipam import (
    assign_ip,
    edit_ip,
    lock_ip,
    next_free_ip_query,
    release_ip,
    validate_foreign_references,
)


router = APIRouter(
    prefix="/ip-addresses",
    tags=["IP Addresses"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[IPAddressRead])
def list_ip_addresses(
    prefix_id: int | None = None,
    subnet_id: int | None = None,
    ip_status: IPStatus | None = Query(default=None, alias="status"),
    q: str | None = Query(default=None, min_length=1, max_length=255),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=256, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    query = select(IPAddress)
    if prefix_id is not None:
        query = query.where(IPAddress.prefix_id == prefix_id)
    if subnet_id is not None:
        query = query.where(IPAddress.subnet_id == subnet_id)
    if ip_status is not None:
        query = query.where(IPAddress.status == ip_status)
    if q:
        term = f"%{q.strip()}%"
        query = (
            query.outerjoin(Device, IPAddress.device_id == Device.id)
            .outerjoin(Customer, IPAddress.customer_id == Customer.id)
            .outerjoin(Router, IPAddress.router_id == Router.id)
            .where(
                or_(
                    IPAddress.address.ilike(term),
                    IPAddress.hostname.ilike(term),
                    IPAddress.mac_address.ilike(term),
                    IPAddress.purpose.ilike(term),
                    IPAddress.notes.ilike(term),
                    Device.name.ilike(term),
                    Customer.name.ilike(term),
                    Router.name.ilike(term),
                )
            )
        )
    return list(db.scalars(query.order_by(IPAddress.address_int).offset(skip).limit(limit)))


@router.get("/next-available", response_model=IPAddressRead)
def find_next_available_ip(
    prefix_id: int,
    subnet_id: int | None = None,
    db: Session = Depends(get_db),
):
    if subnet_id is not None:
        subnet = db.get(Subnet, subnet_id)
        if subnet is None or subnet.prefix_id != prefix_id:
            raise HTTPException(status_code=422, detail="Subnet does not belong to prefix")
    ip = db.scalar(next_free_ip_query(prefix_id=prefix_id, subnet_id=subnet_id))
    if ip is None:
        raise HTTPException(status_code=404, detail="No free IP address is available")
    return ip


@router.post("/next-available/assign", response_model=IPAddressRead)
def assign_next_available_ip(
    payload: NextIPAssignmentRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    fields = payload.model_dump(exclude={"prefix_id", "subnet_id", "status"}, exclude_unset=True)
    # Take inventory KEY SHARE locks before the prefix/IP lock hierarchy.  This
    # matches inventory deletion's row-first order and avoids a delete/assign
    # deadlock while retaining the service-level validation as defence in depth.
    validate_foreign_references(db, fields)
    prefix = db.scalar(
        select(Prefix).where(Prefix.id == payload.prefix_id).with_for_update()
    )
    if prefix is None:
        raise HTTPException(status_code=404, detail="Prefix not found")
    if payload.subnet_id is not None:
        subnet = db.scalar(
            select(Subnet).where(Subnet.id == payload.subnet_id).with_for_update()
        )
        if subnet is None or subnet.prefix_id != payload.prefix_id:
            raise HTTPException(status_code=422, detail="Subnet does not belong to prefix")
    ip = db.scalar(
        next_free_ip_query(prefix_id=payload.prefix_id, subnet_id=payload.subnet_id).with_for_update(
            skip_locked=True
        )
    )
    if ip is None:
        raise HTTPException(status_code=404, detail="No free IP address is available")
    assign_ip(db, ip=ip, fields=fields, status=payload.status, actor=actor)
    write_audit(
        db,
        action=AuditAction.IP_ASSIGNED,
        actor=actor,
        entity_type="ip_address",
        entity_id=ip.id,
        details={"address": ip.address, "status": ip.status.value, "automatic": True},
        request=request,
    )
    db.commit()
    db.refresh(ip)
    return ip


@router.get("/{ip_id}", response_model=IPAddressRead)
def get_ip_address(ip_id: int, db: Session = Depends(get_db)):
    ip = db.get(IPAddress, ip_id)
    if ip is None:
        raise HTTPException(status_code=404, detail="IP address not found")
    return ip


@router.post("/{ip_id}/assign", response_model=IPAddressRead)
def assign_address(
    ip_id: int,
    payload: AssignIPRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    fields = payload.model_dump(exclude={"status"}, exclude_unset=True)
    validate_foreign_references(db, fields)
    ip = lock_ip(db, ip_id)
    assign_ip(db, ip=ip, fields=fields, status=payload.status, actor=actor)
    write_audit(
        db,
        action=AuditAction.IP_ASSIGNED,
        actor=actor,
        entity_type="ip_address",
        entity_id=ip.id,
        details={"address": ip.address, "status": ip.status.value},
        request=request,
    )
    db.commit()
    db.refresh(ip)
    return ip


@router.post("/{ip_id}/reserve", response_model=IPAddressRead)
def reserve_address(
    ip_id: int,
    payload: ReserveIPRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    fields = payload.model_dump(exclude_unset=True)
    if "purpose" not in fields:
        fields["purpose"] = payload.purpose
    validate_foreign_references(db, fields)
    ip = lock_ip(db, ip_id)
    assign_ip(
        db,
        ip=ip,
        fields=fields,
        status=IPStatus.RESERVED,
        actor=actor,
        action=AllocationAction.RESERVED,
    )
    write_audit(
        db,
        action=AuditAction.IP_RESERVED,
        actor=actor,
        entity_type="ip_address",
        entity_id=ip.id,
        details={"address": ip.address},
        request=request,
    )
    db.commit()
    db.refresh(ip)
    return ip


@router.patch("/{ip_id}", response_model=IPAddressRead)
def modify_address(
    ip_id: int,
    payload: EditIPRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    fields = payload.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=422, detail="At least one field must be supplied")
    validate_foreign_references(db, fields)
    ip = lock_ip(db, ip_id)
    edit_ip(db, ip=ip, fields=fields, actor=actor)
    write_audit(
        db,
        action=AuditAction.IP_MODIFIED,
        actor=actor,
        entity_type="ip_address",
        entity_id=ip.id,
        details={"address": ip.address, "changed_fields": sorted(fields)},
        request=request,
    )
    db.commit()
    db.refresh(ip)
    return ip


@router.post("/{ip_id}/release", response_model=IPAddressRead)
def release_address(
    ip_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    ip = lock_ip(db, ip_id)
    prior_status = ip.status.value
    release_ip(db, ip=ip, actor=actor)
    write_audit(
        db,
        action=AuditAction.IP_RELEASED,
        actor=actor,
        entity_type="ip_address",
        entity_id=ip.id,
        details={"address": ip.address, "previous_status": prior_status},
        request=request,
    )
    db.commit()
    db.refresh(ip)
    return ip


@router.get("/{ip_id}/history", response_model=list[AllocationRead])
def address_history(
    ip_id: int,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    if db.get(IPAddress, ip_id) is None:
        raise HTTPException(status_code=404, detail="IP address not found")
    return list(
        db.scalars(
            select(Allocation)
            .where(Allocation.ip_address_id == ip_id)
            .order_by(Allocation.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
    )
