"""
Domain Entity — Analyst Approval.

Represents a pending action request that requires human analyst
review before execution. Part of the detection → alerting →
approval → execution workflow.
"""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Optional


class ApprovalStatus(str, enum.Enum):
    """Status of an analyst approval request."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ActionType(str, enum.Enum):
    """Type of action requiring analyst approval."""

    BLOCK_PORT = "block_port"
    SUSPEND_PROCESS = "suspend_process"
    ISOLATE_NETWORK = "isolate_network"


@dataclass
class Approval:
    """An analyst approval request with lifecycle tracking."""

    id: int = 0
    action_type: str = ActionType.SUSPEND_PROCESS.value
    target_identifier: str = ""
    reason: str = ""
    status: str = ApprovalStatus.PENDING.value
    risk_score: int = 0
    created_at: float = field(default_factory=time.time)
    resolved_at: Optional[float] = None
    resolved_by: Optional[str] = None

    @property
    def is_pending(self) -> bool:
        return self.status == ApprovalStatus.PENDING.value

    @property
    def is_resolved(self) -> bool:
        return self.status in (
            ApprovalStatus.APPROVED.value,
            ApprovalStatus.REJECTED.value,
        )

    def resolve(self, status: str, resolved_by: str = "system") -> None:
        """Resolve this approval request."""
        if status not in (ApprovalStatus.APPROVED.value, ApprovalStatus.REJECTED.value):
            raise ValueError(f"Invalid resolution status: {status!r}")
        self.status = status
        self.resolved_at = time.time()
        self.resolved_by = resolved_by

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "action_type": self.action_type,
            "target_identifier": self.target_identifier,
            "reason": self.reason,
            "status": self.status,
            "risk_score": self.risk_score,
            "resolved_at": self.resolved_at,
            "resolved_by": self.resolved_by,
        }
