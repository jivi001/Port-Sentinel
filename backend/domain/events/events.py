"""
Domain Events — Event definitions for the event-driven architecture.

Events flow through the system in this order:
    PortDetected → ThreatAnalyzed → PolicyEvaluated → FirewallUpdated → NotificationGenerated

All domain events are immutable dataclasses carrying the minimum
data needed for downstream handlers to act.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DomainEvent:
    """Base class for all domain events."""

    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    event_type: str = ""


@dataclass(frozen=True)
class PortDetected(DomainEvent):
    """Emitted when new port traffic data is processed from shared memory."""

    event_type: str = "port_detected"
    port: int = 0
    pid: int = 0
    app_name: str = "Unknown"
    protocol: str = "TCP"
    kb_s_in: float = 0.0
    kb_s_out: float = 0.0
    remote_ip: str = "0.0.0.0"
    risk_score: int = 0


@dataclass(frozen=True)
class ThreatAnalyzed(DomainEvent):
    """Emitted after threat intelligence enriches a connection's IP metadata."""

    event_type: str = "threat_analyzed"
    ip: str = ""
    port: int = 0
    risk_score: int = 0
    org: str = "Unknown"
    country: str = "??"
    is_malicious: bool = False


@dataclass(frozen=True)
class PolicyEvaluated(DomainEvent):
    """Emitted when a policy rule matches a port snapshot."""

    event_type: str = "policy_evaluated"
    policy_id: str = ""
    policy_name: str = ""
    action: str = "notify"
    target_port: int = 0
    target_pid: int = 0
    app_name: str = "Unknown"
    risk_score: int = 0


@dataclass(frozen=True)
class FirewallUpdated(DomainEvent):
    """Emitted when a firewall rule is created or removed."""

    event_type: str = "firewall_updated"
    port: int = 0
    action: str = "block"  # "block" | "unblock"
    protocol: str = "TCP"
    reason: str = ""
    success: bool = True


@dataclass(frozen=True)
class ApprovalRequested(DomainEvent):
    """Emitted when an analyst approval is created."""

    event_type: str = "approval_requested"
    approval_id: int = 0
    action_type: str = ""
    target_identifier: str = ""
    reason: str = ""
    risk_score: int = 0


@dataclass(frozen=True)
class ApprovalResolved(DomainEvent):
    """Emitted when an analyst resolves a pending approval."""

    event_type: str = "approval_resolved"
    approval_id: int = 0
    status: str = ""
    resolved_by: str = "system"


@dataclass(frozen=True)
class AuditLogged(DomainEvent):
    """Emitted when a security-relevant action is recorded in the audit log."""

    event_type: str = "audit_logged"
    log_event_type: str = ""
    message: str = ""
    severity: str = "info"
    app_name: Optional[str] = None
    port: Optional[int] = None
    pid: Optional[int] = None
    details: Optional[str] = None
