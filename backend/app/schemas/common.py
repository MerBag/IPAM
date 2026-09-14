import re
from ipaddress import IPv4Address, IPv4Network
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, model_validator


MAC_PATTERN = re.compile(r"^(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StrictPatchModel(BaseModel):
    """Reject explicit JSON null for database columns that are not nullable.

    Update fields remain optional by omission while avoiding delayed integrity errors.
    """

    non_nullable_fields: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_nulls(cls, value):
        if isinstance(value, dict):
            invalid = sorted(
                field for field in cls.non_nullable_fields if field in value and value[field] is None
            )
            if invalid:
                raise ValueError(f"Fields may not be null: {', '.join(invalid)}")
        return value


class Message(BaseModel):
    message: str


def canonical_ipv4(value: str) -> str:
    return str(IPv4Address(value))


def canonical_network(value: str, *, strict: bool = True) -> str:
    return str(IPv4Network(value, strict=strict))


def normalize_mac(value: str | None) -> str | None:
    if value is None or value == "":
        return None
    candidate = value.replace("-", ":").upper()
    if not MAC_PATTERN.fullmatch(candidate):
        raise ValueError("MAC address must use six hexadecimal octets")
    return candidate
