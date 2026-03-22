"""
Sentinel Policy Engine — Automated Incident Response.

Evaluates real-time metrics and threat intelligence flags against
user-defined policies. Triggers automated actions (kill, block, suspend).
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Callable, Optional

logger = logging.getLogger("sentinel.policies")

@dataclass
class Policy:
    """Definition of an automated response rule."""
    id: str
    name: str
    description: str
    enabled: bool = True
    
    # Conditions
    min_kb_s: float = 0.0
    min_risk_score: int = 0
    target_app: Optional[str] = None  # None = any app
    exclude_apps: List[str] = None
    
    # Action
    action: str = "notify"  # "kill", "block", "suspend", "notify"
    
    def __post_init__(self):
        if self.exclude_apps is None:
            self.exclude_apps = []

class PolicyEngine:
    """
    Core engine for evaluating and executing automation rules.
    """
    def __init__(self, action_handler: Callable[[str, Any, Optional[str]], Any]):
        self.policies: List[Policy] = []
        self._action_handler = action_handler
        self._last_trigger: Dict[str, float] = {}  # policy_id:port -> last_triggered
        self._cooldown = 60  # Prevent rapid re-triggering (seconds)
        
        # Load default safety policies
        self._load_defaults()

    def _load_defaults(self):
        """Pre-load essential security policies."""
        # Cleaned: Removed default mock policies. 
        # Future rules can be loaded from a production-vetted JSON config.
        pass

    def evaluate(self, snapshot: Any):
        """
        Evaluate a single PortSnapshot against all active policies.
        
        Args:
            snapshot: PortSnapshot instance from metrics.py
        """
        for policy in self.policies:
            if not policy.enabled:
                continue
                
            trigger_key = f"{policy.id}:{snapshot.port}"
            now = time.time()
            
            # Cooldown check
            if now - self._last_trigger.get(trigger_key, 0) < self._cooldown:
                continue

            # Check conditions
            match = True
            
            if snapshot.risk_score < policy.min_risk_score:
                match = False
            
            total_kb_s = snapshot.kb_s_in + snapshot.kb_s_out
            if total_kb_s < policy.min_kb_s:
                match = False
                
            if policy.target_app and snapshot.app_name.lower() != policy.target_app.lower():
                match = False
                
            if snapshot.app_name.lower() in [a.lower() for a in policy.exclude_apps]:
                match = False
                
            if match:
                self._trigger_action(policy, snapshot)
                self._last_trigger[trigger_key] = now

    def _trigger_action(self, policy: Policy, snapshot: Any):
        """Execute the automated response."""
        logger.warning(f"POLICY TRIGGERED: '{policy.name}' on {snapshot.app_name} (Port {snapshot.port})")
        
        try:
            if policy.action == "kill":
                self._action_handler("kill", snapshot.pid, snapshot.app_name)
            elif policy.action == "block":
                self._action_handler("block", snapshot.port, snapshot.app_name)
            elif policy.action == "suspend":
                self._action_handler("suspend", snapshot.pid, snapshot.app_name)
            
            # Note: Notifications are handled by the caller or UI
        except Exception as e:
            logger.error(f"Failed to execute policy action {policy.action}: {e}")
