"""
Dependency Injection Container — Typed service registry.

Replaces the global mutable singletons from core/state.py with
a single, typed container that is initialized during startup and
passed to all components via FastAPI's dependency injection.

This is the ONLY place in the application where concrete implementations
are wired to their interfaces.
"""

from __future__ import annotations

import logging
import platform
from typing import Optional

from backend.application.events.bus import EventBus
from backend.application.jobs.scheduler import JobScheduler
from backend.application.services.metrics_service import TrafficAccumulator
from backend.domain.policies.engine import PolicyEngine
from backend.infrastructure.config.settings import Settings
from backend.infrastructure.database.repository import DatabaseRepository
from backend.plugins.registry import PluginRegistry

logger = logging.getLogger("vigilant.container")


class Container:
    """
    Application-wide dependency container.

    Initialized once during application startup. All services are
    accessed through this container rather than global variables.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

        # Core services
        self.event_bus = EventBus()
        self.database = DatabaseRepository(db_url=settings.db_url)
        self.traffic_accumulator = TrafficAccumulator()
        self.policy_engine = PolicyEngine()
        self.job_scheduler = JobScheduler()
        self.plugin_registry = PluginRegistry()

        # Infrastructure — initialized lazily or during startup
        self.os_bridge: Optional[object] = None
        self.sniffer_process: Optional[object] = None
        self.threat_service: Optional[object] = None
        self.influx_writer: Optional[object] = None

        logger.info("Container initialized")

    def wire_os_bridge(self) -> None:
        """Detect and wire the appropriate OS bridge adapter."""
        system = platform.system()
        try:
            if system == "Windows":
                from backend.os_adapters.win32_bridge import WindowsBridge
                self.os_bridge = WindowsBridge()
            elif system == "Linux":
                from backend.os_adapters.linux_bridge import LinuxBridge
                self.os_bridge = LinuxBridge()
            elif system == "Darwin":
                from backend.os_adapters.darwin_bridge import DarwinBridge
                self.os_bridge = DarwinBridge()
            else:
                logger.warning("No OS bridge available for %s", system)
                return

            logger.info("OS bridge wired: %s (%s)", system, type(self.os_bridge).__name__)
        except ImportError:
            logger.warning("OS bridge import failed for %s", system)

    def wire_threat_service(self) -> None:
        """Initialize the threat intelligence service."""
        try:
            from backend.core.threat_intel import ThreatIntel
            self.threat_service = ThreatIntel()
            self.traffic_accumulator.set_threat_service(self.threat_service)
            logger.info("Threat intelligence service wired")
        except Exception:
            logger.warning("Threat intel service not available", exc_info=True)

    def wire_influx(self) -> None:
        """Initialize InfluxDB if configured."""
        if not self.settings.influx_enabled:
            return
        try:
            from backend.core.db import InfluxDBWriter
            self.influx_writer = InfluxDBWriter(
                url=self.settings.influx_url,
                token=self.settings.influx_token,
                org=self.settings.influx_org,
                bucket=self.settings.influx_bucket,
            )
            logger.info("InfluxDB writer wired")
        except Exception:
            logger.warning("InfluxDB not available", exc_info=True)

    def wire_sniffer(self) -> None:
        """Initialize the packet capture process."""
        try:
            from backend.core.sniffer import SnifferProcess
            self.sniffer_process = SnifferProcess(
                shm_name=self.settings.shm_name,
                hmac_key=self.settings.hmac_key.encode("utf-8"),
            )
            logger.info("Sniffer process wired")
        except Exception:
            logger.warning("Sniffer process not available", exc_info=True)

    def register_background_jobs(self) -> None:
        """Register periodic background jobs."""
        db = self.database
        accumulator = self.traffic_accumulator

        # Traffic data persistence (every 30s)
        def flush_traffic() -> None:
            port_table = accumulator.get_port_table()
            if port_table:
                db.insert_traffic(port_table)

        self.job_scheduler.register(
            "traffic_flush", flush_traffic,
            interval_seconds=self.settings.db_flush_interval,
        )

        # Cache eviction (every hour)
        self.job_scheduler.register(
            "cache_evict", accumulator.cleanup,
            interval_seconds=self.settings.cache_evict_interval,
        )

        # Traffic pruning (every hour)
        self.job_scheduler.register(
            "traffic_prune",
            lambda: db.prune_old_traffic(24),
            interval_seconds=3600.0,
        )

        logger.info("Background jobs registered")

    def shutdown(self) -> None:
        """Gracefully shut down all services."""
        logger.info("Container shutdown initiated")

        self.job_scheduler.stop()
        self.plugin_registry.stop_all()

        if self.sniffer_process and hasattr(self.sniffer_process, "stop"):
            self.sniffer_process.stop()

        # Cleanup firewall rules
        if self.os_bridge and hasattr(self.os_bridge, "cleanup_all_rules"):
            try:
                count = self.os_bridge.cleanup_all_rules()
                logger.info("Cleaned up %d firewall rules", count)
            except Exception:
                logger.warning("Firewall cleanup failed", exc_info=True)

        self.database.close()
        self.event_bus.clear()

        logger.info("Container shutdown complete")
