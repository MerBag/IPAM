from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator

from app.enums import AllocationAction, IPStatus, SubnetStatus
from app.schemas.common import ORMModel, StrictPatchModel, canonical_network, normalize_mac


class PrefixCreate(BaseModel):
    cidr: str
    description: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=255)

    @field_validator("cidr")
    @classmethod
    def valid_cidr(cls, value: str) -> str:
        return canonical_network(value)


class PrefixUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=255)


class PrefixRead(ORMModel):
    id: int
    cidr: str
    network_address: str
    broadcast_address: str
    prefix_length: int
    first_usable_ip: str
    last_usable_ip: str
    total_addresses: int
    used_addresses: int = 0
    free_addresses: int = 0
    utilization_percent: float = 0
    description: str | None
    location: str | None
    created_at: datetime
    updated_at: datetime


class SubnetCreate(BaseModel):
    prefix_id: int
    cidr: str
    parent_subnet_id: int | None = None
    status: SubnetStatus = SubnetStatus.FREE
    description: str | None = Field(default=None, max_length=4000)
    vlan: int | None = Field(default=None, ge=1, le=4094)
    location: str | None = Field(default=None, max_length=255)

    @field_validator("cidr")
    @classmethod
    def valid_cidr(cls, value: str) -> str:
        return canonical_network(value)

    @model_validator(mode="after")
    def leaf_status(self):
        if self.status == SubnetStatus.CONTAINER:
            raise ValueError("new leaf subnet status cannot be container")
        return self


class SubnetUpdate(StrictPatchModel):
    non_nullable_fields = frozenset({"status"})
    status: SubnetStatus | None = None
    description: str | None = Field(default=None, max_length=4000)
    vlan: int | None = Field(default=None, ge=1, le=4094)
    location: str | None = Field(default=None, max_length=255)


class SubnetRead(ORMModel):
    id: int
    prefix_id: int
    parent_subnet_id: int | None
    cidr: str
    network_address: str
    broadcast_address: str
    prefix_length: int
    first_usable_ip: str
    last_usable_ip: str
    total_addresses: int
    used_addresses: int = 0
    free_addresses: int = 0
    utilization_percent: float = 0
    status: SubnetStatus
    description: str | None
    vlan: int | None
    location: str | None
    created_at: datetime
    updated_at: datetime


class SplitRequest(BaseModel):
    new_prefix_length: int = Field(ge=1, le=32)


class SplitPreview(BaseModel):
    parent_cidr: str
    new_prefix_length: int
    count: int
    subnets: list[str]


class NextSubnetRequest(BaseModel):
    prefix_id: int
    prefix_length: int = Field(ge=1, le=32)
    status: SubnetStatus = SubnetStatus.ALLOCATED
    description: str | None = Field(default=None, max_length=4000)
    vlan: int | None = Field(default=None, ge=1, le=4094)
    location: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def allocatable_status(self):
        if self.status not in {SubnetStatus.ALLOCATED, SubnetStatus.RESERVED}:
            raise ValueError("status must be allocated or reserved")
        return self


class NextSubnetPreview(BaseModel):
    cidr: str
    subnet_id: int | None = None
    parent_subnet_id: int | None = None
    already_materialized: bool


class IPAssignmentFields(BaseModel):
    hostname: str | None = Field(default=None, max_length=253)
    device_id: int | None = None
    customer_id: int | None = None
    purpose: str | None = Field(default=None, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    router_id: int | None = None
    interface: str | None = Field(default=None, max_length=128)
    vlan: int | None = Field(default=None, ge=1, le=4094)
    mac_address: str | None = None
    notes: str | None = Field(default=None, max_length=10000)
    reverse_dns: str | None = Field(default=None, max_length=253)

    @field_validator("mac_address")
    @classmethod
    def valid_mac(cls, value: str | None) -> str | None:
        return normalize_mac(value)


class AssignIPRequest(IPAssignmentFields):
    status: IPStatus = IPStatus.ASSIGNED

    @model_validator(mode="after")
    def assignable_status(self):
        if self.status not in {IPStatus.ASSIGNED, IPStatus.GATEWAY, IPStatus.BLACKHOLED}:
            raise ValueError("status must be assigned, gateway, or blackholed")
        return self


class ReserveIPRequest(IPAssignmentFields):
    purpose: str | None = Field(default="Reserved", max_length=255)


class EditIPRequest(IPAssignmentFields):
    status: IPStatus | None = None

    @model_validator(mode="after")
    def status_is_mutable(self):
        if self.status in {IPStatus.FREE, IPStatus.NETWORK, IPStatus.BROADCAST}:
            raise ValueError("free, network, and broadcast statuses are system-managed")
        return self


class NextIPAssignmentRequest(AssignIPRequest):
    prefix_id: int
    subnet_id: int | None = None


class IPAddressRead(ORMModel):
    id: int
    prefix_id: int
    subnet_id: int | None
    address: str
    status: IPStatus
    reserved_by_subnet: bool = False
    hostname: str | None
    device_id: int | None
    customer_id: int | None
    purpose: str | None
    location: str | None
    router_id: int | None
    interface: str | None
    vlan: int | None
    mac_address: str | None
    notes: str | None
    reverse_dns: str | None
    date_assigned: datetime | None
    assigned_by_id: int | None
    created_at: datetime
    updated_at: datetime


class AllocationRead(ORMModel):
    id: int
    ip_address_id: int
    subnet_id: int | None
    action: AllocationAction
    previous_status: IPStatus | None
    new_status: IPStatus
    snapshot: dict
    actor_id: int | None
    created_at: datetime


class DashboardSummary(BaseModel):
    total_ips: int
    used_ips: int
    free_ips: int
    reserved_ips: int
    utilization_percent: float
    subnets: int
    devices: int
    recent_assignments: list[AllocationRead]


class SearchResult(BaseModel):
    entity_type: str
    id: int
    primary: str
    secondary: str | None = None
    status: str | None = None
