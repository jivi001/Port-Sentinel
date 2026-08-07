"""
Domain Entity — Threat and ThreatIndicator.

Represents geo-located threat intelligence data enriched
from remote IP addresses observed in network traffic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ThreatIndicator:
    """IP reputation and metadata from threat intelligence feeds."""

    ip: str
    org: str = "Unknown"
    city: str = "Unknown"
    country: str = "??"
    latitude: float = 0.0
    longitude: float = 0.0
    risk: int = 0
    is_malicious: bool = False

    @property
    def is_private(self) -> bool:
        return (
            not self.ip
            or self.ip.startswith("127.")
            or self.ip.startswith("192.168.")
            or self.ip.startswith("10.")
            or self.ip == "0.0.0.0"
        )

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "org": self.org,
            "city": self.city,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "risk": self.risk,
        }


@dataclass
class Threat:
    """A geo-located threat event combining traffic data with threat intelligence."""

    ip: str
    port: int
    app_name: str = "Unknown"
    city: str = "Unknown"
    country: str = "??"
    latitude: float = 0.0
    longitude: float = 0.0
    risk: int = 0
    org: str = "Unknown"
    kb_s_in: float = 0.0
    kb_s_out: float = 0.0
    protocol: str = "TCP"

    def to_dict(self) -> dict:
        return {
            "ip": self.ip,
            "city": self.city,
            "country": self.country,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "risk": self.risk,
            "org": self.org,
            "port": self.port,
            "app_name": self.app_name,
            "kb_s_in": self.kb_s_in,
            "kb_s_out": self.kb_s_out,
            "protocol": self.protocol,
        }
