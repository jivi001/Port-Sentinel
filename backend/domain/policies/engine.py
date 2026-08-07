"""
Domain Policy Engine — Pure rule evaluation.

Evaluates real-time port snapshots against configured policy rules.
This is a pure domain component with no infrastructure dependencies.
Side effects (blocking ports, creating approvals) are published as
domain events for application-layer handlers to execute.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from backend.domain.entities.rule import PolicyRule
from backend.domain.events.events import PolicyEvaluated

logger = logging.getLogger("vigilant.domain.policies")


class PolicyEngine:
    """
    Core engine for evaluating automated response rules.

    Evaluates port snapshot data against all enabled policies and
    emits PolicyEvaluated events when rules trigger. The engine
    is stateless except for cooldown tracking to prevent rapid re-triggering.
    """

    def __init__(
        self,
        on_trigger: Optional[Callable[[PolicyEvaluated], None]] = None,
    ) -> None:
        self.policies: List[PolicyRule] = []
        self._on_trigger = on_trigger
        self._last_trigger: Dict[str, float] = {}
        self._cooldown: int = 60  # Seconds between re-triggers per policy:port

    def evaluate(self, snapshot: Any) -> Optional[PolicyEvaluated]:
        """
        Evaluate a PortSnapshot against all active policies.

        Args:
            snapshot: Object with .port, .pid, .app_name, .kb_s_in,
                      .kb_s_out, .risk_score attributes.

        Returns:
            PolicyEvaluated event if a policy triggered, else None.
        """
        for policy in self.policies:
            if not policy.enabled:
                continue

            trigger_key = f"{policy.id}:{snapshot.port}"
            now = time.time()

            # Cooldown check
            if now - self._last_trigger.get(trigger_key, 0) < self._cooldown:
                continue

            # Evaluate conditions
            if not policy.matches_risk(snapshot.risk_score):
                continue

            total_kb_s = snapshot.kb_s_in + snapshot.kb_s_out
            if not policy.matches_traffic(total_kb_s):
                continue

            if not policy.matches_app(snapshot.app_name):
                continue

            # All conditions met — emit event
            event = PolicyEvaluated(
                policy_id=policy.id,
                policy_name=policy.name,
                action=policy.action,
                target_port=snapshot.port,
                target_pid=snapshot.pid,
                app_name=snapshot.app_name,
                risk_score=snapshot.risk_score,
            )

            logger.warning(
                "POLICY TRIGGERED: '%s' on %s (Port %d)",
                policy.name,
                snapshot.app_name,
                snapshot.port,
            )

            self._last_trigger[trigger_key] = now

            if self._on_trigger:
                self._on_trigger(event)

            return event

        return None

    def add_policy(self, policy: PolicyRule) -> None:
        """Add a policy rule to the engine."""
        self.policies.append(policy)

    def remove_policy(self, policy_id: str) -> bool:
        """Remove a policy by ID. Returns True if found and removed."""
        before = len(self.policies)
        self.policies = [p for p in self.policies if p.id != policy_id]
        return len(self.policies) < before

    def set_cooldown(self, seconds: int) -> None:
        """Set the cooldown period between re-triggers."""
        self._cooldown = max(1, seconds)
