from ipaddress import IPv4Network

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import admin_required, get_current_user, operator_required
from app.enums import AuditAction
from app.models import Allocation, IPAddress, Prefix, Subnet, User
from app.schemas.ipam import PrefixCreate, PrefixRead, PrefixUpdate, SplitPreview, SplitRequest, SubnetRead
from app.services.audit import write_audit
from app.services.ipam import (
    create_prefix,
    prefix_with_stats,
    split_preview,
    split_subnet,
    subnets_with_stats,
)


router = APIRouter(prefix="/prefixes", tags=["Prefixes"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[PrefixRead])
def list_prefixes(db: Session = Depends(get_db)):
    prefixes = list(db.scalars(select(Prefix).order_by(Prefix.network_int)))
    return [prefix_with_stats(db, prefix) for prefix in prefixes]


@router.post("", response_model=PrefixRead, status_code=201)
def add_prefix(
    payload: PrefixCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    try:
        prefix = create_prefix(
            db,
            cidr=payload.cidr,
            description=payload.description,
            location=payload.location,
            actor=actor,
        )
        write_audit(
            db,
            action=AuditAction.PREFIX_CREATED,
            actor=actor,
            entity_type="prefix",
            entity_id=prefix.id,
            details={"cidr": prefix.cidr},
            request=request,
        )
        root_id = db.scalar(
            select(Subnet.id).where(Subnet.prefix_id == prefix.id, Subnet.parent_subnet_id.is_(None))
        )
        write_audit(
            db,
            action=AuditAction.SUBNET_CREATED,
            actor=actor,
            entity_type="subnet",
            entity_id=root_id,
            details={"cidr": prefix.cidr, "root": True},
            request=request,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Prefix already exists")
    db.refresh(prefix)
    return prefix_with_stats(db, prefix)


@router.get("/{prefix_id}", response_model=PrefixRead)
def get_prefix(prefix_id: int, db: Session = Depends(get_db)):
    prefix = db.get(Prefix, prefix_id)
    if prefix is None:
        raise HTTPException(status_code=404, detail="Prefix not found")
    return prefix_with_stats(db, prefix)


@router.patch("/{prefix_id}", response_model=PrefixRead)
def update_prefix(
    prefix_id: int,
    payload: PrefixUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    prefix = db.scalar(select(Prefix).where(Prefix.id == prefix_id).with_for_update())
    if prefix is None:
        raise HTTPException(status_code=404, detail="Prefix not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one field must be supplied")
    for key, value in changes.items():
        setattr(prefix, key, value)
    write_audit(
        db,
        action=AuditAction.PREFIX_MODIFIED,
        actor=actor,
        entity_type="prefix",
        entity_id=prefix.id,
        details={"cidr": prefix.cidr, "changed_fields": sorted(changes)},
        request=request,
    )
    db.commit()
    db.refresh(prefix)
    return prefix_with_stats(db, prefix)


@router.delete("/{prefix_id}", status_code=204)
def delete_prefix(
    prefix_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(admin_required),
):
    prefix = db.scalar(select(Prefix).where(Prefix.id == prefix_id).with_for_update())
    if prefix is None:
        raise HTTPException(status_code=404, detail="Prefix not found")
    has_history = db.scalar(
        select(Allocation.id)
        .join(IPAddress, Allocation.ip_address_id == IPAddress.id)
        .where(IPAddress.prefix_id == prefix_id)
        .limit(1)
    )
    if has_history:
        raise HTTPException(
            status_code=409,
            detail="Prefix has allocation history and cannot be deleted",
        )
    write_audit(
        db,
        action=AuditAction.PREFIX_DELETED,
        actor=actor,
        entity_type="prefix",
        entity_id=prefix.id,
        details={"cidr": prefix.cidr},
        request=request,
    )
    for subnet in db.scalars(select(Subnet).where(Subnet.prefix_id == prefix_id)):
        write_audit(
            db,
            action=AuditAction.SUBNET_DELETED,
            actor=actor,
            entity_type="subnet",
            entity_id=subnet.id,
            details={"cidr": subnet.cidr, "reason": "prefix_deleted"},
            request=request,
        )
    # Flush the delete before the audit commit so database constraints fail atomically.
    db.delete(prefix)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{prefix_id}/subnets", response_model=list[SubnetRead])
def prefix_subnets(prefix_id: int, db: Session = Depends(get_db)):
    if db.get(Prefix, prefix_id) is None:
        raise HTTPException(status_code=404, detail="Prefix not found")
    subnets = list(
        db.scalars(
            select(Subnet).where(Subnet.prefix_id == prefix_id).order_by(Subnet.network_int, Subnet.prefix_length)
        )
    )
    return subnets_with_stats(db, subnets)


@router.get("/{prefix_id}/split-preview", response_model=SplitPreview)
def preview_prefix_split(
    prefix_id: int,
    new_prefix_length: int = Query(ge=1, le=32),
    db: Session = Depends(get_db),
):
    prefix = db.get(Prefix, prefix_id)
    if prefix is None:
        raise HTTPException(status_code=404, detail="Prefix not found")
    cidrs = split_preview(prefix.cidr, new_prefix_length)
    return SplitPreview(
        parent_cidr=prefix.cidr,
        new_prefix_length=new_prefix_length,
        count=len(cidrs),
        subnets=cidrs,
    )


@router.post("/{prefix_id}/split", response_model=list[SubnetRead], status_code=201)
def persist_prefix_split(
    prefix_id: int,
    payload: SplitRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    root = db.scalar(
        select(Subnet).where(Subnet.prefix_id == prefix_id, Subnet.parent_subnet_id.is_(None))
    )
    if root is None:
        raise HTTPException(status_code=404, detail="Prefix not found")
    _, children = split_subnet(
        db,
        subnet_id=root.id,
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
            details={"cidr": child.cidr, "parent_id": root.id},
            request=request,
        )
    db.commit()
    return subnets_with_stats(db, children)
