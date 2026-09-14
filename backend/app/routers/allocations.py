from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Allocation
from app.schemas.ipam import AllocationRead


router = APIRouter(
    prefix="/allocations",
    tags=["Allocation History"],
    dependencies=[Depends(get_current_user)],
)


@router.get("", response_model=list[AllocationRead])
def list_allocations(
    ip_address_id: int | None = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = select(Allocation)
    if ip_address_id is not None:
        query = query.where(Allocation.ip_address_id == ip_address_id)
    return list(
        db.scalars(query.order_by(Allocation.created_at.desc()).offset(skip).limit(limit))
    )
