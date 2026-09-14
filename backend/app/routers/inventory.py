from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, operator_required
from app.enums import AuditAction
from app.models import Customer, Device, IPAddress, Router, User
from app.schemas.inventory import (
    CustomerCreate,
    CustomerRead,
    CustomerUpdate,
    DeviceCreate,
    DeviceRead,
    DeviceUpdate,
    RouterCreate,
    RouterRead,
    RouterUpdate,
)
from app.services.audit import write_audit


router = APIRouter(tags=["Inventory"], dependencies=[Depends(get_current_user)])


def _commit_unique(db: Session, message: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=message)


def _flush_unique(db: Session, message: str) -> None:
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=message)


def _commit_delete(db: Session, entity_name: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"{entity_name} became referenced by an IP address; clear or reassign associations first",
        )


def _with_ip_counts(db: Session, items: list, foreign_key) -> list[dict]:
    if not items:
        return []
    ids = [item.id for item in items]
    counts = dict(
        db.execute(
            select(foreign_key, func.count(IPAddress.id))
            .where(foreign_key.in_(ids))
            .group_by(foreign_key)
        ).all()
    )
    return [
        {
            **{column.name: getattr(item, column.name) for column in item.__table__.columns},
            "ip_count": int(counts.get(item.id, 0)),
        }
        for item in items
    ]


@router.get("/devices", response_model=list[DeviceRead])
def list_devices(
    q: str | None = Query(default=None, min_length=1, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = select(Device)
    if q:
        term = f"%{q.strip()}%"
        query = query.where(
            or_(
                Device.name.ilike(term),
                Device.management_ip.ilike(term),
                Device.mac_address.ilike(term),
                Device.location.ilike(term),
                Device.description.ilike(term),
            )
        )
    items = list(db.scalars(query.order_by(Device.name).offset(skip).limit(limit)))
    return _with_ip_counts(db, items, IPAddress.device_id)


@router.get("/devices/{item_id}", response_model=DeviceRead)
def get_device(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Device, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Device not found")
    return _with_ip_counts(db, [item], IPAddress.device_id)[0]


@router.post("/devices", response_model=DeviceRead, status_code=201)
def create_device(
    payload: DeviceCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    item = Device(**payload.model_dump())
    db.add(item)
    _flush_unique(db, "A device with this name already exists")
    write_audit(
        db,
        action=AuditAction.DEVICE_CREATED,
        actor=actor,
        entity_type="device",
        entity_id=item.id,
        details={"name": item.name, "type": item.type.value},
        request=request,
    )
    _commit_unique(db, "A device with this name already exists")
    db.refresh(item)
    return _with_ip_counts(db, [item], IPAddress.device_id)[0]


@router.patch("/devices/{item_id}", response_model=DeviceRead)
def update_device(
    item_id: int,
    payload: DeviceUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    item = db.get(Device, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Device not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one field must be supplied")
    for key, value in changes.items():
        setattr(item, key, value)
    write_audit(
        db,
        action=AuditAction.DEVICE_MODIFIED,
        actor=actor,
        entity_type="device",
        entity_id=item.id,
        details={"name": item.name, "changed_fields": sorted(changes)},
        request=request,
    )
    _commit_unique(db, "A device with this name already exists")
    db.refresh(item)
    return _with_ip_counts(db, [item], IPAddress.device_id)[0]


@router.delete("/devices/{item_id}", status_code=204)
def delete_device(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    # Serialize against IP assignment, which takes a PostgreSQL KEY SHARE lock
    # while validating this foreign key.  The RESTRICT constraint remains the
    # final line of defence if a reference is introduced concurrently.
    item = db.scalar(select(Device).where(Device.id == item_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Device not found")
    if db.scalar(select(IPAddress.id).where(IPAddress.device_id == item.id).limit(1)):
        raise HTTPException(
            status_code=409,
            detail="Device is referenced by an IP address; clear or reassign associations first",
        )
    write_audit(
        db,
        action=AuditAction.DEVICE_DELETED,
        actor=actor,
        entity_type="device",
        entity_id=item.id,
        details={"name": item.name},
        request=request,
    )
    db.delete(item)
    _commit_delete(db, "Device")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/customers", response_model=list[CustomerRead])
def list_customers(
    q: str | None = Query(default=None, min_length=1, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = select(Customer)
    if q:
        term = f"%{q.strip()}%"
        query = query.where(
            or_(
                Customer.name.ilike(term),
                Customer.contact_name.ilike(term),
                Customer.email.ilike(term),
                Customer.phone.ilike(term),
                Customer.account_reference.ilike(term),
                Customer.notes.ilike(term),
            )
        )
    items = list(db.scalars(query.order_by(Customer.name).offset(skip).limit(limit)))
    return _with_ip_counts(db, items, IPAddress.customer_id)


@router.get("/customers/{item_id}", response_model=CustomerRead)
def get_customer(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Customer, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    return _with_ip_counts(db, [item], IPAddress.customer_id)[0]


@router.post("/customers", response_model=CustomerRead, status_code=201)
def create_customer(
    payload: CustomerCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    item = Customer(**payload.model_dump(mode="json"))
    db.add(item)
    _flush_unique(db, "Customer name or account reference already exists")
    write_audit(
        db,
        action=AuditAction.CUSTOMER_CREATED,
        actor=actor,
        entity_type="customer",
        entity_id=item.id,
        details={"name": item.name, "account_reference": item.account_reference},
        request=request,
    )
    _commit_unique(db, "Customer name or account reference already exists")
    db.refresh(item)
    return _with_ip_counts(db, [item], IPAddress.customer_id)[0]


@router.patch("/customers/{item_id}", response_model=CustomerRead)
def update_customer(
    item_id: int,
    payload: CustomerUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    item = db.get(Customer, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    changes = payload.model_dump(exclude_unset=True, mode="json")
    if not changes:
        raise HTTPException(status_code=422, detail="At least one field must be supplied")
    for key, value in changes.items():
        setattr(item, key, value)
    write_audit(
        db,
        action=AuditAction.CUSTOMER_MODIFIED,
        actor=actor,
        entity_type="customer",
        entity_id=item.id,
        details={"name": item.name, "changed_fields": sorted(changes)},
        request=request,
    )
    _commit_unique(db, "Customer name or account reference already exists")
    db.refresh(item)
    return _with_ip_counts(db, [item], IPAddress.customer_id)[0]


@router.delete("/customers/{item_id}", status_code=204)
def delete_customer(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    item = db.scalar(select(Customer).where(Customer.id == item_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if db.scalar(select(IPAddress.id).where(IPAddress.customer_id == item.id).limit(1)):
        raise HTTPException(
            status_code=409,
            detail="Customer is referenced by an IP address; clear or reassign associations first",
        )
    write_audit(
        db,
        action=AuditAction.CUSTOMER_DELETED,
        actor=actor,
        entity_type="customer",
        entity_id=item.id,
        details={"name": item.name},
        request=request,
    )
    db.delete(item)
    _commit_delete(db, "Customer")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/routers", response_model=list[RouterRead])
def list_routers(
    q: str | None = Query(default=None, min_length=1, max_length=100),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = select(Router)
    if q:
        term = f"%{q.strip()}%"
        query = query.where(
            or_(
                Router.name.ilike(term),
                Router.management_ip.ilike(term),
                Router.username.ilike(term),
                Router.location.ilike(term),
                Router.notes.ilike(term),
            )
        )
    items = list(db.scalars(query.order_by(Router.name).offset(skip).limit(limit)))
    return _with_ip_counts(db, items, IPAddress.router_id)


@router.get("/routers/{item_id}", response_model=RouterRead)
def get_router(item_id: int, db: Session = Depends(get_db)):
    item = db.get(Router, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Router not found")
    return _with_ip_counts(db, [item], IPAddress.router_id)[0]


@router.post("/routers", response_model=RouterRead, status_code=201)
def create_router(
    payload: RouterCreate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    item = Router(**payload.model_dump())
    db.add(item)
    _flush_unique(db, "Router name or management IP already exists")
    write_audit(
        db,
        action=AuditAction.ROUTER_CREATED,
        actor=actor,
        entity_type="router",
        entity_id=item.id,
        details={"name": item.name, "management_ip": item.management_ip},
        request=request,
    )
    _commit_unique(db, "Router name or management IP already exists")
    db.refresh(item)
    return _with_ip_counts(db, [item], IPAddress.router_id)[0]


@router.patch("/routers/{item_id}", response_model=RouterRead)
def update_router(
    item_id: int,
    payload: RouterUpdate,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    item = db.get(Router, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Router not found")
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one field must be supplied")
    for key, value in changes.items():
        setattr(item, key, value)
    write_audit(
        db,
        action=AuditAction.ROUTER_MODIFIED,
        actor=actor,
        entity_type="router",
        entity_id=item.id,
        details={"name": item.name, "changed_fields": sorted(changes)},
        request=request,
    )
    _commit_unique(db, "Router name or management IP already exists")
    db.refresh(item)
    return _with_ip_counts(db, [item], IPAddress.router_id)[0]


@router.delete("/routers/{item_id}", status_code=204)
def delete_router(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    actor: User = Depends(operator_required),
):
    item = db.scalar(select(Router).where(Router.id == item_id).with_for_update())
    if item is None:
        raise HTTPException(status_code=404, detail="Router not found")
    if db.scalar(select(IPAddress.id).where(IPAddress.router_id == item.id).limit(1)):
        raise HTTPException(
            status_code=409,
            detail="Router is referenced by an IP address; clear or reassign associations first",
        )
    write_audit(
        db,
        action=AuditAction.ROUTER_DELETED,
        actor=actor,
        entity_type="router",
        entity_id=item.id,
        details={"name": item.name},
        request=request,
    )
    db.delete(item)
    _commit_delete(db, "Router")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
