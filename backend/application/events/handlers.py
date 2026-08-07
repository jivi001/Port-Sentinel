"""
Application Event Handlers — Wire domain events to side effects.

Handlers listen for domain events published by the event bus and
execute the appropriate application-level actions (database writes,
audit logging, firewall operations, etc.).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.domain.events.events import (
    FirewallUpdated,
    PolicyEvaluated,
    ApprovalRequested,
    ApprovalResolved,
    AuditLogged,
)

if TYPE_CHECKING:
    from backend.container import Container

logger = logging.getLogger("vigilant.events.handlers")


class EventHandlers:
    """
    Registers and manages domain event handlers.

    All handlers receive a domain event and interact with infrastructure
    through the DI container.
    """

    def __init__(self, container: "Container") -> None:
        self._container = container

    def register_all(self) -> None:
        """Register all event handlers on the event bus."""
        bus = self._container.event_bus

        bus.subscribe(PolicyEvaluated, self._on_policy_evaluated)
        bus.subscribe(FirewallUpdated, self._on_firewall_updated)
        bus.subscribe(AuditLogged, self._on_audit_logged)

        logger.info("Event handlers registered (%d total)", bus.handler_count)

    def _on_policy_evaluated(self, event: PolicyEvaluated) -> None:
        """Handle automated policy triggers — execute block or request approval."""
        db = self._container.database
        os_bridge = self._container.os_bridge

        try:
            if event.action == "block" and os_bridge:
                os_bridge.block_port(event.target_port)
                db.add_blocked_port(
                    event.target_port,
                    block_type="hard",
                    reason="Policy Engine Auto-Block",
                )
                severity = "critical"
                msg = f"Automated block triggered on Port {event.target_port}"
            elif event.action == "request_approval":
                db.create_analyst_approval(
                    action_type="suspend_process",
                    target_identifier=str(event.target_pid),
                    reason="Policy trigger",
                )
                severity = "warning"
                msg = f"Analyst Approval requested for PID {event.target_pid}"
            else:
                severity = "info"
                msg = f"Policy '{event.policy_name}' notification for {event.app_name}"

            db.insert_audit_log(
                event_type="policy_trigger",
                message=msg,
                app_name=event.app_name,
                severity=severity,
                details=f"Action: {event.action}, Port: {event.target_port}, PID: {event.target_pid}",
            )
        except Exception:
            logger.exception("Policy action handler failed for event %s", event.event_id)

    def _on_firewall_updated(self, event: FirewallUpdated) -> None:
        """Log firewall rule changes to the audit trail."""
        db = self._container.database
        try:
            db.insert_audit_log(
                event_type=f"firewall_{event.action}",
                message=f"Firewall {event.action} on port {event.port}/{event.protocol}",
                port=event.port,
                severity="critical" if event.action == "block" else "warning",
                details=f"Reason: {event.reason}, Success: {event.success}",
            )
        except Exception:
            logger.exception("Firewall audit log failed")

    def _on_audit_logged(self, event: AuditLogged) -> None:
        """Persist audit log events to the database."""
        db = self._container.database
        try:
            db.insert_audit_log(
                event_type=event.log_event_type,
                message=event.message,
                app_name=event.app_name,
                port=event.port,
                pid=event.pid,
                severity=event.severity,
                details=event.details,
            )
        except Exception:
            logger.exception("Audit persistence failed")
