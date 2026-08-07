"""
CQRS Queries — Dashboard and system read operations.

Queries are pure read operations that aggregate data from
multiple sources without mutating state.
"""

from __future__ import annotations

import os
import platform
import threading
import time
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import psutil

if TYPE_CHECKING:
    from backend.container import Container

logger = logging.getLogger("vigilant.queries.dashboard")

_start_time = time.time()


@dataclass(frozen=True)
class DashboardQuery:
    """Query for the full dashboard overview."""
    pass


@dataclass(frozen=True)
class SystemHealthQuery:
    """Lightweight health check query."""
    pass


@dataclass(frozen=True)
class SystemInfoQuery:
    """Detailed system information query."""
    pass


@dataclass(frozen=True)
class SystemMetricsQuery:
    """Real-time system metrics (CPU, memory, network)."""
    pass


class DashboardQueryHandler:
    """Handles dashboard and system information queries."""

    PRODUCT_NAME = "Vigilant"
    PRODUCT_FULL_NAME = "Vigilant Enterprise Network Defense"
    VERSION = "2.0.0"

    def __init__(self, container: "Container") -> None:
        self._container = container

    def handle_health(self, query: SystemHealthQuery) -> dict:
        """Lightweight health check."""
        sniffer = self._container.sniffer_process
        accumulator = self._container.traffic_accumulator

        return {
            "status": "ok",
            "product": self.PRODUCT_NAME,
            "version": self.VERSION,
            "platform": platform.system(),
            "sniffer_alive": sniffer.is_alive() if sniffer else False,
            "ports_tracked": accumulator.cache.port_count() if accumulator else 0,
            "uptime_seconds": round(time.time() - _start_time, 2),
        }

    def handle_info(self, query: SystemInfoQuery) -> dict:
        """Detailed system information dashboard."""
        sniffer = self._container.sniffer_process
        accumulator = self._container.traffic_accumulator
        policy_engine = self._container.policy_engine
        p = psutil.Process(os.getpid())

        return {
            "system": {
                "name": self.PRODUCT_FULL_NAME,
                "version": self.VERSION,
                "status": "Operational",
                "platform": platform.system(),
                "uptime_seconds": round(time.time() - _start_time, 2),
            },
            "resources": {
                "cpu_usage_percent": psutil.cpu_percent(),
                "memory_usage_mb": round(p.memory_info().rss / (1024 * 1024), 2),
                "threads_active": threading.active_count(),
            },
            "engine": {
                "sniffer_active": sniffer.is_alive() if sniffer else False,
                "ports_monitored": accumulator.cache.port_count() if accumulator else 0,
                "policies_loaded": len(policy_engine.policies) if policy_engine else 0,
            },
            "endpoints": {
                "api_health": "/api/health",
                "api_ports": "/api/ports",
                "api_blocked": "/api/blocked",
                "interactive_docs": "/docs",
            },
        }

    def handle_metrics(self, query: SystemMetricsQuery) -> dict:
        """Real-time system resource metrics."""
        p = psutil.Process(os.getpid())
        net = psutil.net_io_counters()
        accumulator = self._container.traffic_accumulator
        db = self._container.database
        sniffer = self._container.sniffer_process

        # Count active connections and listening ports
        connections = 0
        listening = 0
        try:
            for conn in psutil.net_connections(kind="inet"):
                if conn.status == "ESTABLISHED":
                    connections += 1
                elif conn.status == "LISTEN":
                    listening += 1
        except (psutil.AccessDenied, PermissionError):
            pass

        blocked_count = len(db.get_blocked_ports()) if db else 0

        # Count suspicious (high-risk) processes from port table
        suspicious = 0
        if accumulator:
            port_table = accumulator.get_port_table()
            suspicious = len([p for p in port_table if p.get("risk_score", 0) >= 7])

        return {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_used_mb": round(p.memory_info().rss / (1024 * 1024), 2),
            "net_bytes_sent": net.bytes_sent,
            "net_bytes_recv": net.bytes_recv,
            "active_connections": connections,
            "listening_ports": listening,
            "blocked_ports": blocked_count,
            "suspicious_processes": suspicious,
            "sniffer_active": sniffer.is_alive() if sniffer else False,
            "uptime_seconds": round(time.time() - _start_time, 2),
        }
