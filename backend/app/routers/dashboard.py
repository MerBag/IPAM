from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.enums import AllocationAction, IPStatus
from app.models import Allocation, Device, IPAddress, Subnet
from app.schemas.ipam import DashboardSummary


router = APIRouter(
    prefix="/dashboard", tags=["Dashboard"], dependencies=[Depends(get_current_user)]
)


@router.get("", response_model=DashboardSummary)
def dashboard(db: Session = Depends(get_db)):
    counts = dict(
        db.execute(select(IPAddress.status, func.count(IPAddress.id)).group_by(IPAddress.status)).all()
    )
    total = int(sum(counts.values()))
    free = int(counts.get(IPStatus.FREE, 0))
    reserved = int(counts.get(IPStatus.RESERVED, 0))
    used = total - free
    subnets = int(db.scalar(select(func.count(Subnet.id))) or 0)
    devices = int(db.scalar(select(func.count(Device.id))) or 0)
    recent = list(
        db.scalars(
            select(Allocation)
            .where(Allocation.action.in_([AllocationAction.ASSIGNED, AllocationAction.RESERVED]))
            .order_by(Allocation.created_at.desc())
            .limit(10)
        )
    )
    return DashboardSummary(
        total_ips=total,
        used_ips=used,
        free_ips=free,
        reserved_ips=reserved,
        utilization_percent=round((used / total) * 100, 2) if total else 0,
        subnets=subnets,
        devices=devices,
        recent_assignments=recent,
    )
