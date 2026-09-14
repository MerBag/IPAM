"""Non-destructive extension boundary for future RouterOS integration.

No RouterOS client is instantiated by the first release. In particular, route or
address mutation is deliberately unavailable until an authenticated provider,
approval policy, and reconciliation tests are added.
"""

from dataclasses import dataclass, field
from typing import Protocol, Sequence


@dataclass(frozen=True)
class RouterOSAddress:
    address: str
    interface: str | None = None
    comment: str | None = None
    disabled: bool = False


@dataclass(frozen=True)
class ReconciliationReport:
    unknown_addresses: list[RouterOSAddress] = field(default_factory=list)
    missing_addresses: list[str] = field(default_factory=list)
    duplicate_addresses: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BlackholeRoutePlan:
    router_id: int
    prefix: str
    operation: str
    destructive_actions_enabled: bool = False


class MikroTikProvider(Protocol):
    async def discover_addresses(self, router_id: int) -> Sequence[RouterOSAddress]:
        """Read configured addresses from one router without changing it."""
        ...

    async def compare_assignments(
        self, router_id: int, expected_addresses: Sequence[str]
    ) -> ReconciliationReport:
        """Compare RouterOS observations with IPAM's expected state."""
        ...

    async def propose_import(self, router_id: int) -> Sequence[RouterOSAddress]:
        """Return import candidates; persistence remains an explicit IPAM operation."""
        ...

    async def plan_blackhole_route(
        self, router_id: int, prefix: str, *, remove: bool = False
    ) -> BlackholeRoutePlan:
        """Build a reviewable plan only; the interface exposes no route mutation."""
        ...


class DisabledMikroTikProvider:
    """Safe default registered until RouterOS support is configured."""

    async def discover_addresses(self, router_id: int) -> Sequence[RouterOSAddress]:
        raise NotImplementedError("MikroTik discovery is not configured")

    async def compare_assignments(
        self, router_id: int, expected_addresses: Sequence[str]
    ) -> ReconciliationReport:
        raise NotImplementedError("MikroTik reconciliation is not configured")

    async def propose_import(self, router_id: int) -> Sequence[RouterOSAddress]:
        raise NotImplementedError("MikroTik import is not configured")

    async def plan_blackhole_route(
        self, router_id: int, prefix: str, *, remove: bool = False
    ) -> BlackholeRoutePlan:
        raise NotImplementedError("MikroTik blackhole route planning is not configured")

    async def manage_blackhole_route(self, *args, **kwargs) -> None:
        raise PermissionError("Destructive RouterOS actions are disabled")


mikrotik_provider: MikroTikProvider = DisabledMikroTikProvider()
