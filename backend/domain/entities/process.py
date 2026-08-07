"""
Domain Entity — Network Process.

Represents an operating system process that has active
network connections, used for the process control view.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Set


@dataclass
class NetworkProcess:
    """A process with active network connections."""

    pid: int
    app_name: str = "Unknown"
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    ports: Set[int] = field(default_factory=set)
    kb_s_in: float = 0.0
    kb_s_out: float = 0.0
    risk_score: int = 0
    status: str = "running"
    create_time: float = 0.0

    @property
    def is_system(self) -> bool:
        """Return True for protected system PIDs."""
        return self.pid in (0, 1, 4)

    @property
    def kb_s_total(self) -> float:
        return round(self.kb_s_in + self.kb_s_out, 2)

    @property
    def port_count(self) -> int:
        return len(self.ports)
