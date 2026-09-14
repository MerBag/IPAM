from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.enums import DeviceType
from app.schemas.common import ORMModel, StrictPatchModel, canonical_ipv4, normalize_mac


class DeviceBase(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    type: DeviceType = DeviceType.OTHER
    management_ip: str | None = None
    mac_address: str | None = None
    location: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=4000)

    @field_validator("management_ip")
    @classmethod
    def valid_ip(cls, value: str | None) -> str | None:
        return canonical_ipv4(value) if value else None

    @field_validator("mac_address")
    @classmethod
    def valid_mac(cls, value: str | None) -> str | None:
        return normalize_mac(value)


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(StrictPatchModel):
    non_nullable_fields = frozenset({"name", "type"})
    name: str | None = Field(default=None, min_length=1, max_length=128)
    type: DeviceType | None = None
    management_ip: str | None = None
    mac_address: str | None = None
    location: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=4000)

    _valid_ip = field_validator("management_ip")(DeviceBase.valid_ip.__func__)
    _valid_mac = field_validator("mac_address")(DeviceBase.valid_mac.__func__)


class DeviceRead(DeviceBase, ORMModel):
    id: int
    ip_count: int = 0
    created_at: datetime
    updated_at: datetime


class CustomerBase(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    contact_name: str | None = Field(default=None, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    account_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=4000)


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(StrictPatchModel):
    non_nullable_fields = frozenset({"name"})
    name: str | None = Field(default=None, min_length=1, max_length=160)
    contact_name: str | None = Field(default=None, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=50)
    account_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=4000)


class CustomerRead(CustomerBase, ORMModel):
    id: int
    ip_count: int = 0
    created_at: datetime
    updated_at: datetime


class RouterBase(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    management_ip: str
    api_port: int = Field(default=8728, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=128)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)
    enabled: bool = False

    @field_validator("management_ip")
    @classmethod
    def valid_ip(cls, value: str) -> str:
        return canonical_ipv4(value)


class RouterCreate(RouterBase):
    pass


class RouterUpdate(StrictPatchModel):
    non_nullable_fields = frozenset({"name", "management_ip", "api_port", "enabled"})
    name: str | None = Field(default=None, min_length=1, max_length=128)
    management_ip: str | None = None
    api_port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=128)
    location: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=4000)
    enabled: bool | None = None

    @field_validator("management_ip")
    @classmethod
    def valid_ip(cls, value: str | None) -> str | None:
        return canonical_ipv4(value) if value else None


class RouterRead(RouterBase, ORMModel):
    id: int
    ip_count: int = 0
    created_at: datetime
    updated_at: datetime
