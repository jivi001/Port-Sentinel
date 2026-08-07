"""
Infrastructure Network — Async dispatcher loop.

Reads from shared memory, processes raw byte counters via the
traffic accumulator, and emits Socket.IO updates.
"""

from __future__ import annotations

import asyncio
import logging
import multiprocessing.shared_memory as shm
import struct
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.container import Container

logger = logging.getLogger("vigilant.network.dispatcher")

# Shared Memory Layout Constants (matching core/constants.py)
ENTRY_SIZE = 32
SHM_SIZE = 1000 * ENTRY_SIZE
PORT_ENTRY_FMT = "<IQQII"


class Dispatcher:
    """
    Reads from the sniffer's shared memory, processes traffic,
    and publishes Socket.IO updates.
    """

    def __init__(self, container: "Container") -> None:
        self._container = container
        self._running = False
        self._task = None

    def start(self) -> None:
        """Start the async dispatcher loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Network dispatcher loop started")

    def stop(self) -> None:
        """Stop the async dispatcher loop."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Network dispatcher loop stopped")

    async def _run_loop(self) -> None:
        """Main dispatcher loop."""
        accumulator = self._container.traffic_accumulator
        settings = self._container.settings
        shm_name = settings.shm_name
        interval = settings.emit_interval

        try:
            from backend.presentation.websocket.handlers import emit_port_table
        except ImportError:
            logger.error("Failed to import Socket.IO emitter")
            return

        shared_mem = None
        while self._running:
            try:
                if shared_mem is None:
                    try:
                        shared_mem = shm.SharedMemory(name=shm_name)
                    except FileNotFoundError:
                        await asyncio.sleep(0.5)
                        continue

                now = time.time()
                active_count = 0

                from backend.core.sniffer import read_all_active_ports
                active_ports = read_all_active_ports(shared_mem, settings.hmac_key.encode("utf-8"))

                for entry in active_ports:
                    port, bytes_in, bytes_out, pid, protocol, active, risk_score, remote_ip = entry

                    snapshot = accumulator.process_port_data(
                        port=port,
                        bytes_in=bytes_in,
                        bytes_out=bytes_out,
                        pid=pid,
                        protocol=protocol,
                        timestamp=now,
                    )
                    snapshot.remote_ip = remote_ip
                    snapshot.risk_score = risk_score
                    active_count += 1

                    # Trigger policy evaluation
                    event = self._container.policy_engine.evaluate(snapshot)
                    if event:
                        self._container.event_bus.publish(event)

                if active_count > 0:
                    port_table = accumulator.get_port_table(now)
                    await emit_port_table(port_table)

                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Dispatcher loop error")
                await asyncio.sleep(1.0)
            finally:
                if shared_mem and not self._running:
                    shared_mem.close()
