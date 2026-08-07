"""
CQRS Commands — Firewall write operations.

Commands represent intent to mutate state. Each command handler
validates input, performs the operation, and publishes domain events.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from backend.domain.events.events import FirewallUpdated

if TYPE_CHECKING:
    from backend.container import Container

logger = logging.getLogger("vigilant.commands.firewall")


@dataclass(frozen=True)
class BlockPortCommand:
    """Command to block a port via the OS firewall."""

    port: int
    protocol: str = "TCP"
    reason: str = "Manual block"


@dataclass(frozen=True)
class UnblockPortCommand:
    """Command to remove a firewall rule for a port."""

    port: int


class FirewallCommandHandler:
    """Handles firewall-related write commands."""

    def __init__(self, container: "Container") -> None:
        self._container = container

    def handle_block(self, cmd: BlockPortCommand) -> dict:
        """Execute a port block command."""
        os_bridge = self._container.os_bridge
        db = self._container.database
        event_bus = self._container.event_bus

        if not os_bridge:
            return {"success": False, "error": "Unsupported platform"}

        try:
            success = os_bridge.block_port(cmd.port, cmd.protocol)
            if success:
                db.add_blocked_port(
                    cmd.port,
                    block_type="hard",
                    reason=f"User blocked {cmd.protocol}",
                )
                event_bus.publish(
                    FirewallUpdated(
                        port=cmd.port,
                        action="block",
                        protocol=cmd.protocol,
                        reason=cmd.reason,
                        success=True,
                    )
                )
            return {"success": success, "port": cmd.port, "action": "block"}
        except Exception as exc:
            logger.error("Firewall block error for port %d: %s", cmd.port, exc)
            raise

    def handle_unblock(self, cmd: UnblockPortCommand) -> dict:
        """Execute a port unblock command."""
        os_bridge = self._container.os_bridge
        db = self._container.database
        event_bus = self._container.event_bus

        if not os_bridge:
            return {"success": False, "error": "Unsupported platform"}

        success = os_bridge.unblock_port(cmd.port)
        if success:
            db.remove_blocked_port(cmd.port)
            event_bus.publish(
                FirewallUpdated(
                    port=cmd.port,
                    action="unblock",
                    reason="Manual unblock",
                    success=True,
                )
            )
        return {"success": success, "port": cmd.port, "action": "unblock"}
