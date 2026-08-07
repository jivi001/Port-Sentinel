"""
CQRS Commands — Approval workflow write operations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from backend.domain.events.events import ApprovalRequested, ApprovalResolved

if TYPE_CHECKING:
    from backend.container import Container

logger = logging.getLogger("vigilant.commands.approvals")


@dataclass(frozen=True)
class RequestApprovalCommand:
    """Command to request analyst approval for a process action."""

    pid: int
    app_name: Optional[str] = None
    reason: str = "Manual request"


@dataclass(frozen=True)
class ResolveApprovalCommand:
    """Command to resolve a pending approval as approved or rejected."""

    approval_id: int
    status: str  # "approved" | "rejected"
    resolved_by: str = "system"


class ApprovalCommandHandler:
    """Handles approval workflow write commands."""

    def __init__(self, container: "Container") -> None:
        self._container = container

    def handle_request(self, cmd: RequestApprovalCommand) -> dict:
        """Create a new analyst approval request."""
        db = self._container.database
        event_bus = self._container.event_bus

        approval_id = db.create_analyst_approval(
            action_type="suspend_process",
            target_identifier=str(cmd.pid),
            reason=cmd.reason,
        )

        event_bus.publish(
            ApprovalRequested(
                approval_id=approval_id,
                action_type="suspend_process",
                target_identifier=str(cmd.pid),
                reason=cmd.reason,
            )
        )

        db.insert_audit_log(
            event_type="approval_requested",
            message=f"Approval requested for PID {cmd.pid}",
            severity="info",
            details=f"App: {cmd.app_name}, Reason: {cmd.reason}, Approval ID: {approval_id}",
        )

        return {
            "success": True,
            "pid": cmd.pid,
            "action": "request_approval",
            "approval_id": approval_id,
        }

    def handle_resolve(self, cmd: ResolveApprovalCommand) -> dict:
        """Resolve a pending approval."""
        db = self._container.database
        event_bus = self._container.event_bus

        success = db.update_approval_status(
            cmd.approval_id, cmd.status, cmd.resolved_by
        )
        if not success:
            return {"success": False, "error": "Approval not found"}

        event_bus.publish(
            ApprovalResolved(
                approval_id=cmd.approval_id,
                status=cmd.status,
                resolved_by=cmd.resolved_by,
            )
        )

        severity = "info" if cmd.status == "approved" else "warning"
        db.insert_audit_log(
            event_type="approval_resolved",
            message=f"Approval {cmd.approval_id} {cmd.status} by {cmd.resolved_by}",
            severity=severity,
            details=f"Approval ID: {cmd.approval_id}, Status: {cmd.status}",
        )

        return {
            "success": True,
            "approval_id": cmd.approval_id,
            "status": cmd.status,
        }
