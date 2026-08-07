"""
Domain Entity — Policy Rule.

Represents an automated response rule evaluated against
real-time port snapshots by the PolicyEngine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PolicyRule:
    """An automated incident response rule."""

    id: str
    name: str
    description: str
    enabled: bool = True

    # Trigger conditions
    min_kb_s: float = 0.0
    min_risk_score: int = 0
    target_app: Optional[str] = None
    exclude_apps: List[str] = field(default_factory=list)

    # Response action: "request_approval" | "block" | "notify"
    action: str = "notify"

    def matches_app(self, app_name: str) -> bool:
        """Check if the rule applies to the given application."""
        if app_name.lower() in [a.lower() for a in self.exclude_apps]:
            return False
        if self.target_app and app_name.lower() != self.target_app.lower():
            return False
        return True

    def matches_traffic(self, total_kb_s: float) -> bool:
        """Check if the traffic volume exceeds the threshold."""
        return total_kb_s >= self.min_kb_s

    def matches_risk(self, risk_score: int) -> bool:
        """Check if the risk score meets the minimum threshold."""
        return risk_score >= self.min_risk_score
