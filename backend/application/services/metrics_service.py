"""
Application Service — Metrics accumulation and traffic processing.

Wraps the PortMetrics delta calculator and SlidingWindowCache from the
original core/metrics.py. This is the primary service consumed by the
dispatcher loop to transform raw byte counters into KB/s rates.
"""

from __future__ import annotations

import sys
import time
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger("vigilant.services.metrics")

# 24h at 1Hz = 86,400 entries max per port
MAX_WINDOW_ENTRIES = 86_400
ACTIVE_PORT_TTL_SECONDS = 5.0


@dataclass
class PortSnapshot:
    """A single point-in-time snapshot of a port's traffic."""

    timestamp: float
    port: int
    pid: int
    app_name: str
    kb_s_in: float
    kb_s_out: float
    protocol: str  # "TCP" or "UDP"
    direction: str  # "both"
    risk_score: int = 0
    remote_ip: str = "0.0.0.0"
    org: str = "Unknown"
    country: str = "??"


@dataclass
class ByteSnapshot:
    """Raw byte counter snapshot used for delta calculation."""

    timestamp: float
    bytes_in: int
    bytes_out: int


class PortMetrics:
    """
    Calculates KB/s deltas from consecutive byte counter snapshots.

    Handles normal delta calculation, zero-traffic edge case,
    and overflow guard (byte counter wrap at sys.maxsize).
    """

    def __init__(self) -> None:
        self._last_snapshot: Dict[int, ByteSnapshot] = {}

    def calculate_delta(
        self,
        port: int,
        current_bytes_in: int,
        current_bytes_out: int,
        current_time: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Calculate KB/s for a port given current byte counters.

        Returns (kb_s_in, kb_s_out). Returns (0.0, 0.0) on first call.
        """
        if current_time is None:
            current_time = time.time()

        prev = self._last_snapshot.get(port)

        self._last_snapshot[port] = ByteSnapshot(
            timestamp=current_time,
            bytes_in=current_bytes_in,
            bytes_out=current_bytes_out,
        )

        if prev is None:
            return 0.0, 0.0

        elapsed = current_time - prev.timestamp
        if elapsed <= 0:
            return 0.0, 0.0

        delta_in = self._safe_delta(current_bytes_in, prev.bytes_in)
        delta_out = self._safe_delta(current_bytes_out, prev.bytes_out)

        kb_s_in = (delta_in / 1024.0) / elapsed
        kb_s_out = (delta_out / 1024.0) / elapsed

        return round(kb_s_in, 2), round(kb_s_out, 2)

    @staticmethod
    def _safe_delta(current: int, previous: int) -> int:
        """Calculate byte delta with overflow guard."""
        if current >= previous:
            return current - previous
        return current + (2**64 - previous)

    def reset(self, port: Optional[int] = None) -> None:
        """Reset cached snapshots for a port or all ports."""
        if port is not None:
            self._last_snapshot.pop(port, None)
        else:
            self._last_snapshot.clear()


class SlidingWindowCache:
    """
    24-hour sliding window cache for traffic history.

    Memory-bounded: uses deque with maxlen per port.
    """

    def __init__(self, max_entries: int = MAX_WINDOW_ENTRIES) -> None:
        self.max_entries = max_entries
        self._cache: Dict[int, deque] = {}

    def add(self, snapshot: PortSnapshot) -> None:
        """Add a traffic snapshot to the cache."""
        port = snapshot.port
        if port not in self._cache:
            self._cache[port] = deque(maxlen=self.max_entries)
        self._cache[port].append(snapshot)

    def get_history(
        self, port: int, seconds: Optional[int] = None
    ) -> List[PortSnapshot]:
        """Get traffic history for a port."""
        if port not in self._cache:
            return []
        entries = self._cache[port]
        if seconds is None:
            return list(entries)
        cutoff = time.time() - seconds
        return [s for s in entries if s.timestamp >= cutoff]

    def evict_stale(self, max_age_seconds: int = 86_400) -> int:
        """Remove entries older than max_age_seconds."""
        cutoff = time.time() - max_age_seconds
        evicted = 0
        for port in list(self._cache.keys()):
            dq = self._cache[port]
            while dq and dq[0].timestamp < cutoff:
                dq.popleft()
                evicted += 1
            if not dq:
                del self._cache[port]
        return evicted

    def port_count(self) -> int:
        return len(self._cache)

    def total_entries(self) -> int:
        return sum(len(dq) for dq in self._cache.values())

    def clear(self) -> None:
        self._cache.clear()


class TrafficAccumulator:
    """
    High-level traffic metric accumulation.

    Combines PortMetrics (delta calc) with SlidingWindowCache (history).
    Called by the Dispatcher to process shared memory data.
    """

    _PID_CACHE_TTL = 60.0
    _PID_CACHE_MAX = 500

    def __init__(self, threat_service: Optional[object] = None) -> None:
        self.metrics = PortMetrics()
        self.cache = SlidingWindowCache()
        self._app_name_cache: Dict[int, tuple] = {}
        self._threat_service = threat_service

    def set_threat_service(self, service: object) -> None:
        """Set the threat intel service (avoids circular init)."""
        self._threat_service = service

    def process_port_data(
        self,
        port: int,
        bytes_in: int,
        bytes_out: int,
        pid: int,
        protocol: int,
        timestamp: Optional[float] = None,
        risk_score: int = 0,
        remote_ip: str = "0.0.0.0",
    ) -> PortSnapshot:
        """Process raw port data into a PortSnapshot with KB/s rates."""
        if timestamp is None:
            timestamp = time.time()

        kb_s_in, kb_s_out = self.metrics.calculate_delta(
            port, bytes_in, bytes_out, timestamp
        )

        app_name = self._resolve_app_name(pid)
        proto_str = "TCP" if protocol == 0 else "UDP"

        # Enrichment: IP Metadata
        meta: dict = {"org": "Unknown", "country": "??", "risk": 0}
        if self._threat_service and hasattr(self._threat_service, "get_ip_metadata"):
            meta = self._threat_service.get_ip_metadata(remote_ip)

        snapshot = PortSnapshot(
            timestamp=timestamp,
            port=port,
            pid=pid,
            app_name=app_name,
            kb_s_in=kb_s_in,
            kb_s_out=kb_s_out,
            protocol=proto_str,
            direction="both",
            risk_score=max(risk_score, meta.get("risk", 0)),
            remote_ip=remote_ip,
            org=meta.get("org", "Unknown"),
            country=meta.get("country", "??"),
        )

        self.cache.add(snapshot)
        return snapshot

    def _resolve_app_name(self, pid: int) -> str:
        """Resolve PID to application name with TTL-based caching."""
        now = time.time()

        if pid in self._app_name_cache:
            name, resolved_at = self._app_name_cache[pid]
            if now - resolved_at < self._PID_CACHE_TTL:
                return name

        if pid in (0, 1, 4):
            name = "System"
        else:
            try:
                proc = psutil.Process(pid)
                name = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                name = "Unknown"

        self._app_name_cache[pid] = (name, now)

        if len(self._app_name_cache) > self._PID_CACHE_MAX:
            self._app_name_cache = {
                k: v
                for k, v in self._app_name_cache.items()
                if now - v[1] < 300
            }

        return name

    def get_port_table(self, current_time: Optional[float] = None) -> List[dict]:
        """Get the current full port table as a list of dicts."""
        if current_time is None:
            current_time = time.time()

        latest: Dict[int, PortSnapshot] = {}
        for port, dq in self.cache._cache.items():
            if dq:
                latest[port] = dq[-1]

        return [
            {
                "port": s.port,
                "pid": s.pid,
                "app_name": s.app_name,
                "kb_s_in": s.kb_s_in,
                "kb_s_out": s.kb_s_out,
                "kb_s": round(s.kb_s_in + s.kb_s_out, 2),
                "protocol": s.protocol,
                "direction": s.direction,
                "risk_score": s.risk_score,
                "remote_ip": s.remote_ip,
                "org": s.org,
                "country": s.country,
                "timestamp": s.timestamp,
            }
            for s in sorted(latest.values(), key=lambda x: x.port)
            if (current_time - s.timestamp) <= ACTIVE_PORT_TTL_SECONDS
        ]

    def cleanup(self) -> None:
        """Evict stale data and free memory."""
        evicted = self.cache.evict_stale()
        if evicted > 0:
            logger.info("Evicted %d stale cache entries", evicted)
