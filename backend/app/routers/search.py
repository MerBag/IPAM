from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Customer, Device, IPAddress, Prefix, Router, Subnet
from app.schemas.ipam import SearchResult


router = APIRouter(prefix="/search", tags=["Search"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[SearchResult])
def global_search(
    q: str = Query(min_length=1, max_length=255),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    term = f"%{q.strip()}%"
    per_type = max(1, min(50, limit))
    results: list[SearchResult] = []
    ips = db.scalars(
        select(IPAddress)
        .outerjoin(Device, IPAddress.device_id == Device.id)
        .outerjoin(Customer, IPAddress.customer_id == Customer.id)
        .outerjoin(Router, IPAddress.router_id == Router.id)
        .where(
            or_(
                IPAddress.address.ilike(term),
                IPAddress.hostname.ilike(term),
                IPAddress.mac_address.ilike(term),
                IPAddress.notes.ilike(term),
                IPAddress.purpose.ilike(term),
                Device.name.ilike(term),
                Customer.name.ilike(term),
                Router.name.ilike(term),
            )
        )
        .order_by(IPAddress.address_int)
        .limit(per_type)
    )
    for ip in ips:
        results.append(
            SearchResult(
                entity_type="ip_address",
                id=ip.id,
                primary=ip.address,
                secondary=ip.hostname or ip.purpose,
                status=ip.status.value,
            )
        )
    for prefix in db.scalars(select(Prefix).where(Prefix.cidr.ilike(term)).limit(per_type)):
        results.append(SearchResult(entity_type="prefix", id=prefix.id, primary=prefix.cidr))
    for subnet in db.scalars(
        select(Subnet).where(or_(Subnet.cidr.ilike(term), Subnet.description.ilike(term))).limit(per_type)
    ):
        results.append(
            SearchResult(
                entity_type="subnet",
                id=subnet.id,
                primary=subnet.cidr,
                secondary=subnet.description,
                status=subnet.status.value,
            )
        )
    devices = db.scalars(
        select(Device)
        .where(
            or_(
                Device.name.ilike(term),
                Device.management_ip.ilike(term),
                Device.mac_address.ilike(term),
                Device.location.ilike(term),
                Device.description.ilike(term),
            )
        )
        .limit(per_type)
    )
    for item in devices:
        results.append(
            SearchResult(
                entity_type="device",
                id=item.id,
                primary=item.name,
                secondary=item.management_ip or item.mac_address or item.location,
            )
        )
    customers = db.scalars(
        select(Customer)
        .where(
            or_(
                Customer.name.ilike(term),
                Customer.contact_name.ilike(term),
                Customer.email.ilike(term),
                Customer.phone.ilike(term),
                Customer.account_reference.ilike(term),
                Customer.notes.ilike(term),
            )
        )
        .limit(per_type)
    )
    for item in customers:
        results.append(
            SearchResult(
                entity_type="customer",
                id=item.id,
                primary=item.name,
                secondary=item.account_reference or item.contact_name,
            )
        )
    routers = db.scalars(
        select(Router)
        .where(
            or_(
                Router.name.ilike(term),
                Router.management_ip.ilike(term),
                Router.username.ilike(term),
                Router.location.ilike(term),
                Router.notes.ilike(term),
            )
        )
        .limit(per_type)
    )
    for item in routers:
        results.append(
            SearchResult(
                entity_type="router",
                id=item.id,
                primary=item.name,
                secondary=item.management_ip or item.location,
            )
        )
    return results[:limit]
