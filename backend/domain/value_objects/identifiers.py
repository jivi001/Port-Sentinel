"""
Domain Value Objects — Typed identifiers.

Newtype wrappers to prevent accidentally mixing up raw integers
that represent different domain concepts (PID vs. approval ID, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProcessId:
    """Operating system process identifier."""

    value: int

    @property
    def is_system(self) -> bool:
        """Return True for protected system PIDs (0, 1, 4)."""
        return self.value in (0, 1, 4)

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ApprovalId:
    """Database identifier for an analyst approval record."""

    value: int

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)
