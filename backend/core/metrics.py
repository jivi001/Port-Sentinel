"""
Sentinel Core Metrics — Delta calculation and sliding window cache.

Converts raw byte counters from shared memory into KB/s rates.
Maintains a 24-hour sliding window cache for historical queries.
"""

import sys
import time
import logging
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Tuple

import psutil

logger = logging.getLogger("sentinel.metrics")

# 24h at 1Hz = 86,400 entries max per port
MAX_WINDOW_ENTRIES = 86_400
OVERFLOW_THRESHOLD = sys.maxsize  # 2^63 - 1 on 64-bit Python


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


@dataclass
class ByteSnapshot:
    """Raw byte counter snapshot used for delta calculation."""
    timestamp: float
    bytes_in: int
    bytes_out: int


class PortMetrics:
    """
    Calculates KB/s deltas from consecutive byte counter snapshots.

    Handles:
      - Normal delta calculation
      - Zero-traffic edge case (0.0 KB/s, no division by zero)
      - Overflow guard (byte counter wrap at sys.maxsize)
    """

    def __init__(self):
        # port -> last ByteSnapshot
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

        Args:
            port: Port number
            current_bytes_in: Current cumulative bytes received
            current_bytes_out: Current cumulative bytes sent
            current_time: Timestamp (defaults to time.time())

        Returns:
            (kb_s_in, kb_s_out) — rates in KB/s. Returns (0.0, 0.0) on first call.
        """
        if current_time is None:
            current_time = time.time()

        prev = self._last_snapshot.get(port)

        # Store current snapshot for next delta
        self._last_snapshot[port] = ByteSnapshot(
            timestamp=current_time,
            bytes_in=current_bytes_in,
            bytes_out=current_bytes_out,
        )

        if prev is None:
            # First snapshot — no delta possible
            return 0.0, 0.0

        elapsed = current_time - prev.timestamp
        if elapsed <= 0:
            # Zero or negative elapsed time — safety guard against division by zero
            return 0.0, 0.0

        # Calculate byte deltas with overflow guard
        delta_in = self._safe_delta(current_bytes_in, prev.bytes_in)
        delta_out = self._safe_delta(current_bytes_out, prev.bytes_out)

        # Convert bytes/interval → KB/s
        kb_s_in = (delta_in / 1024.0) / elapsed
        kb_s_out = (delta_out / 1024.0) / elapsed

        return round(kb_s_in, 2), round(kb_s_out, 2)

    @staticmethod
    def _safe_delta(current: int, previous: int) -> int:
        """
        Calculate byte delta with overflow guard.

        If current < previous, assume the counter wrapped around.
        In that case, we estimate the delta as just the current value
        (assuming the wrap happened once and previous was near max).
        """
        if current >= previous:
            return current - previous
        else:
            # Overflow detected: counter wrapped at 2^64
            # Best-effort: assume single wrap
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

    - Stores up to MAX_WINDOW_ENTRIES (86,400) per port at 1Hz
    - Automatically evicts entries older than 24 hours
    - Memory-bounded: uses deque with maxlen
    """

    def __init__(self, max_entries: int = MAX_WINDOW_ENTRIES):
        self.max_entries = max_entries
        # port -> deque of PortSnapshot
        self._cache: Dict[int, deque] = {}

    def add(self, snapshot: PortSnapshot) -> None:
        """Add a traffic snapshot to the cache for a port."""
        port = snapshot.port
        if port not in self._cache:
            self._cache[port] = deque(maxlen=self.max_entries)
        self._cache[port].append(snapshot)

    def get_history(self, port: int, seconds: Optional[int] = None) -> List[PortSnapshot]:
        """
        Get traffic history for a port.

        Args:
            port: Port number
            seconds: Optional lookback window in seconds (default: all cached)

        Returns:
            List of PortSnapshot entries within the window.
        """
        if port not in self._cache:
            return []

        entries = self._cache[port]
        if seconds is None:
            return list(entries)

        cutoff = time.time() - seconds
        return [s for s in entries if s.timestamp >= cutoff]

    def evict_stale(self, max_age_seconds: int = 86_400) -> int:
        """
        Remove entries older than max_age_seconds across all ports.

        Returns the number of entries evicted.
        """
        cutoff = time.time() - max_age_seconds
        evicted = 0

        for port in list(self._cache.keys()):
            dq = self._cache[port]
            initial_len = len(dq)
            # Evict from left (oldest) while stale
            while dq and dq[0].timestamp < cutoff:
                dq.popleft()
                evicted += 1
            # Remove empty port entries
            if not dq:
                del self._cache[port]

        return evicted

    def port_count(self) -> int:
        """Number of ports currently tracked."""
        return len(self._cache)

    def total_entries(self) -> int:
        """Total number of entries across all ports."""
        return sum(len(dq) for dq in self._cache.values())

    def clear(self) -> None:
        """Clear the entire cache."""
        self._cache.clear()


class TrafficAccumulator:
    """
    High-level traffic metric accumulation.

    Combines PortMetrics (delta calc) with SlidingWindowCache (history).
    Called by the Dispatcher to process shared memory data into UI-ready state.
    """

    def __init__(self):
        self.metrics = PortMetrics()
        self.cache = SlidingWindowCache()
        self._app_name_cache: Dict[int, str] = {}  # pid -> app_name

    def process_port_data(
        self,
        port: int,
        bytes_in: int,
        bytes_out: int,
        pid: int,
        protocol: int,
        timestamp: Optional[float] = None,
    ) -> PortSnapshot:
        """
        Process raw port data into a PortSnapshot with KB/s rates.

        Args:
            port: Port number
            bytes_in: Cumulative bytes received
            bytes_out: Cumulative bytes sent
            pid: Process ID owning this port
            protocol: 0=TCP, 1=UDP
            timestamp: Override timestamp (for testing)

        Returns:
            PortSnapshot with calculated rates.
        """
        if timestamp is None:
            timestamp = time.time()

        kb_s_in, kb_s_out = self.metrics.calculate_delta(
            port, bytes_in, bytes_out, timestamp
        )

        app_name = self._resolve_app_name(pid)
        proto_str = "TCP" if protocol == 0 else "UDP"

        snapshot = PortSnapshot(
            timestamp=timestamp,
            port=port,
            pid=pid,
            app_name=app_name,
            kb_s_in=kb_s_in,
            kb_s_out=kb_s_out,
            protocol=proto_str,
            direction="both",
        )

        self.cache.add(snapshot)
        return snapshot

    def _resolve_app_name(self, pid: int) -> str:
        """Resolve PID to application name with caching."""
        if pid in self._app_name_cache:
            return self._app_name_cache[pid]

        if pid == 0:
            name = "System"
        elif pid == 4:
            name = "System"  # Windows System process
        elif pid == 1:
            name = "System"  # macOS launchd
        else:
            try:
                proc = psutil.Process(pid)
                name = proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                name = "Unknown"

        self._app_name_cache[pid] = name
        return name

    def get_port_table(self) -> List[dict]:
        """
        Get the current full port table as a list of dicts.

        This is what gets serialized to MsgPack and sent to the frontend.
        """
        # Get latest snapshot per port from cache
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
                "timestamp": s.timestamp,
            }
            for s in sorted(latest.values(), key=lambda x: x.port)
        ]

    def cleanup(self) -> None:
        """Evict stale data and free memory."""
        evicted = self.cache.evict_stale()
        if evicted > 0:
            logger.info(f"Evicted {evicted} stale cache entries")
