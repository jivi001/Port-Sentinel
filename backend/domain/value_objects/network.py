"""
Domain Value Objects — Network primitives.

Immutable typed values representing network concepts.
These enforce invariants at construction time and are used
throughout the domain layer instead of raw primitives.
"""

from __future__ import annotations

import enum
import ipaddress
from dataclasses import dataclass


class Protocol(str, enum.Enum):
    """Network transport protocol."""

    TCP = "TCP"
    UDP = "UDP"

    @classmethod
    def from_int(cls, value: int) -> Protocol:
        """Convert sniffer protocol integer (0=TCP, 1=UDP) to enum."""
        return cls.UDP if value == 1 else cls.TCP


@dataclass(frozen=True, slots=True)
class PortNumber:
    """A validated network port number (1–65535)."""

    value: int

    def __post_init__(self) -> None:
        if not 1 <= self.value <= 65535:
            raise ValueError(f"Port number must be 1–65535, got {self.value}")

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class IPAddress:
    """A validated IPv4 or IPv6 address string."""

    value: str

    def __post_init__(self) -> None:
        if self.value and self.value != "0.0.0.0":
            try:
                ipaddress.ip_address(self.value)
            except ValueError as exc:
                raise ValueError(f"Invalid IP address: {self.value!r}") from exc

    @property
    def is_private(self) -> bool:
        """Return True for RFC-1918, loopback, and link-local addresses."""
        if not self.value or self.value == "0.0.0.0":
            return True
        try:
            return ipaddress.ip_address(self.value).is_private
        except ValueError:
            return False

    @property
    def is_loopback(self) -> bool:
        if not self.value:
            return False
        try:
            return ipaddress.ip_address(self.value).is_loopback
        except ValueError:
            return False

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class RiskScore:
    """Threat risk score clamped to 0–10."""

    value: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", max(0, min(10, self.value)))

    @property
    def is_critical(self) -> bool:
        return self.value >= 10

    @property
    def is_high(self) -> bool:
        return self.value >= 7

    @property
    def is_medium(self) -> bool:
        return self.value >= 5

    @property
    def label(self) -> str:
        if self.is_critical:
            return "CRITICAL"
        if self.is_high:
            return "HIGH"
        if self.is_medium:
            return "MEDIUM"
        return "LOW"

    def __int__(self) -> int:
        return self.value

    def __gt__(self, other: object) -> bool:
        if isinstance(other, RiskScore):
            return self.value > other.value
        if isinstance(other, int):
            return self.value > other
        return NotImplemented

    def __ge__(self, other: object) -> bool:
        if isinstance(other, RiskScore):
            return self.value >= other.value
        if isinstance(other, int):
            return self.value >= other
        return NotImplemented
