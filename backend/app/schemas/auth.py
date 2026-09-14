from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.enums import UserRole
from app.schemas.common import ORMModel, StrictPatchModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserRead(ORMModel):
    id: int
    username: str
    role: UserRole
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    password: str = Field(min_length=12, max_length=1024)
    role: UserRole = UserRole.READ_ONLY
    is_active: bool = True


class UserUpdate(StrictPatchModel):
    non_nullable_fields = frozenset({"role", "is_active"})
    role: UserRole | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=12, max_length=1024)
