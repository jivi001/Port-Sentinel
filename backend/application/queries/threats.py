"""
CQRS Queries — Threat intelligence read operations.
"""

from __future__ import annotations

import time
import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from backend.container import Container

logger = logging.getLogger("vigilant.queries.threats")

# Simulated threat data for dev/demo mode when no live connections exist
SIMULATED_THREATS = [
    {"ip": "185.220.101.5", "city": "Berlin", "country": "DE", "latitude": 52.52, "longitude": 13.405, "risk": 8, "org": "Tor Exit Node IP", "port": 443},
    {"ip": "45.147.230.12", "city": "Moscow", "country": "RU", "latitude": 55.7558, "longitude": 37.6173, "risk": 9, "org": "Mirai Botnet Scanner", "port": 23},
    {"ip": "210.22.115.44", "city": "Shanghai", "country": "CN", "latitude": 31.2304, "longitude": 121.4737, "risk": 7, "org": "SSH Brute-Forcer", "port": 22},
    {"ip": "103.20.122.9", "city": "Seoul", "country": "KR", "latitude": 37.5665, "longitude": 126.978, "risk": 6, "org": "Web Vulnerability Scanner", "port": 8080},
    {"ip": "198.51.100.72", "city": "New York", "country": "US", "latitude": 40.7128, "longitude": -74.006, "risk": 5, "org": "Unusual outbound sync", "port": 443},
    {"ip": "101.36.120.10", "city": "Tokyo", "country": "JP", "latitude": 35.6762, "longitude": 139.6503, "risk": 8, "org": "Malicious Command Center", "port": 9001},
]


@dataclass(frozen=True)
class ThreatGeoQuery:
    """Query for geo-referenced active threat data."""
    min_risk: int = 0


@dataclass(frozen=True)
class ThreatCountriesQuery:
    """Query for threat counts grouped by country."""
    pass


@dataclass(frozen=True)
class ThreatTimelineQuery:
    """Query for historical threat events for replay visualization."""
    hours: int = 24


class ThreatQueryHandler:
    """Handles threat intelligence read queries."""

    def __init__(self, container: "Container") -> None:
        self._container = container

    def handle_geo(self, query: ThreatGeoQuery) -> List[dict]:
        """Get geo-referenced active threats with simulated fallback."""
        accumulator = self._container.traffic_accumulator
        threat_intel = self._container.threat_service

        if not accumulator:
            return [t for t in SIMULATED_THREATS if t["risk"] >= query.min_risk]

        now = time.time()
        active_ports = accumulator.get_port_table(now)

        threats: List[dict] = []
        seen_ips: set = set()

        for p in active_ports:
            ip = p.get("remote_ip", "0.0.0.0")
            if ip != "0.0.0.0" and ip not in seen_ips:
                meta = threat_intel.get_ip_metadata(ip) if threat_intel else {}
                risk = max(p.get("risk_score", 0), meta.get("risk", 0))
                if risk >= query.min_risk:
                    seen_ips.add(ip)
                    threats.append({
                        "ip": ip,
                        "city": meta.get("city", "Unknown"),
                        "country": meta.get("country", "??"),
                        "latitude": meta.get("latitude", 0.0),
                        "longitude": meta.get("longitude", 0.0),
                        "risk": risk,
                        "org": meta.get("org", "Unknown"),
                        "port": p.get("port", 0),
                    })

        if not threats:
            return [t for t in SIMULATED_THREATS if t["risk"] >= query.min_risk]

        return threats

    def handle_countries(self, query: ThreatCountriesQuery) -> List[dict]:
        """Get threat counts grouped by country."""
        geo_data = self.handle_geo(ThreatGeoQuery(min_risk=0))
        country_counts: Counter = Counter()
        for t in geo_data:
            country_counts[t["country"]] += 1
        return [
            {"country": country, "count": count}
            for country, count in country_counts.items()
        ]

    def handle_timeline(self, query: ThreatTimelineQuery) -> List[dict]:
        """Get threat events in time buckets for replay visualization."""
        accumulator = self._container.traffic_accumulator
        threat_intel = self._container.threat_service

        if not accumulator:
            return self._simulated_timeline()

        cutoff = time.time() - (query.hours * 3600)
        bucket_size = 300  # 5-minute intervals
        buckets: Dict[int, List[dict]] = {}

        for port, dq in accumulator.cache._cache.items():
            for s in dq:
                if s.timestamp >= cutoff and s.remote_ip != "0.0.0.0":
                    bucket_id = int(s.timestamp / bucket_size) * bucket_size
                    if bucket_id not in buckets:
                        buckets[bucket_id] = []

                    meta = threat_intel.get_ip_metadata(s.remote_ip) if threat_intel else {}
                    buckets[bucket_id].append({
                        "ip": s.remote_ip,
                        "city": meta.get("city", "Unknown"),
                        "country": meta.get("country", "??"),
                        "latitude": meta.get("latitude", 0.0),
                        "longitude": meta.get("longitude", 0.0),
                        "risk": max(s.risk_score, meta.get("risk", 0)),
                        "org": s.org,
                        "port": s.port,
                        "kb_s_in": s.kb_s_in,
                        "kb_s_out": s.kb_s_out,
                    })

        response = [
            {"timestamp": ts, "threats": items}
            for ts, items in sorted(buckets.items())
        ]

        if not response:
            return self._simulated_timeline()

        return response

    @staticmethod
    def _simulated_timeline() -> List[dict]:
        """Generate mock timeline for standalone dev mode."""
        now = time.time()
        return [
            {
                "timestamp": now - (i * 300),
                "threats": [
                    {**t, "kb_s_in": 14.2 * (i % 3 + 1), "kb_s_out": 5.1 * (i % 2 + 1)}
                    for t in SIMULATED_THREATS[: (i % len(SIMULATED_THREATS) + 1)]
                ],
            }
            for i in range(12)
        ]
