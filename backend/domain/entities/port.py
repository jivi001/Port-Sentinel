"""
Domain Entity — Port and Connection.

Represents a network port with associated traffic metrics,
process binding, and threat enrichment data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Port:
    """A monitored network port with real-time traffic data."""

    port: int
    pid: int = 0
    app_name: str = "Unknown"
    protocol: str = "TCP"
    direction: str = "both"
    kb_s_in: float = 0.0
    kb_s_out: float = 0.0
    risk_score: int = 0
    remote_ip: str = "0.0.0.0"
    org: str = "Unknown"
    country: str = "??"
    timestamp: float = 0.0

    @property
    def kb_s_total(self) -> float:
        return round(self.kb_s_in + self.kb_s_out, 2)

    @property
    def is_high_risk(self) -> bool:
        return self.risk_score >= 7

    def to_dict(self) -> dict:
        """Serialize to the wire format expected by the frontend."""
        return {
            "port": self.port,
            "pid": self.pid,
            "app_name": self.app_name,
            "kb_s_in": self.kb_s_in,
            "kb_s_out": self.kb_s_out,
            "kb_s": self.kb_s_total,
            "protocol": self.protocol,
            "direction": self.direction,
            "risk_score": self.risk_score,
            "remote_ip": self.remote_ip,
            "org": self.org,
            "country": self.country,
            "timestamp": self.timestamp,
        }


@dataclass
class Connection:
    """A single network connection with source/destination context."""

    local_port: int
    remote_ip: str
    remote_port: int
    pid: int
    protocol: str = "TCP"
    status: str = "ESTABLISHED"
    app_name: str = "Unknown"
    bytes_in: int = 0
    bytes_out: int = 0
