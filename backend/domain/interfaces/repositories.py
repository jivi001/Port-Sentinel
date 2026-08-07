"""
Domain Interfaces — Repository abstract base classes.

These define the contracts that infrastructure implementations must fulfill.
The domain layer depends only on these interfaces, never on concrete
database or storage implementations.
"""

from __future__ import annotations

import abc
from typing import Any, Dict, List, Optional


class IPortRepository(abc.ABC):
    """Repository for blocked port records."""

    @abc.abstractmethod
    def add_blocked_port(
        self, port: int, block_type: str = "hard", reason: str = ""
    ) -> None: ...

    @abc.abstractmethod
    def remove_blocked_port(self, port: int) -> None: ...

    @abc.abstractmethod
    def get_blocked_ports(self) -> List[dict]: ...

    @abc.abstractmethod
    def clear_blocked_ports(self) -> int: ...


class IHistoryRepository(abc.ABC):
    """Repository for traffic history records."""

    @abc.abstractmethod
    def insert_traffic(self, records: List[Dict[str, Any]]) -> None: ...

    @abc.abstractmethod
    def get_traffic_history(self, port: int, hours: int = 24) -> List[dict]: ...

    @abc.abstractmethod
    def prune_old_traffic(self, max_age_hours: int = 24) -> int: ...

    @abc.abstractmethod
    def get_top_talkers(
        self, hours: int = 24, limit: int = 10
    ) -> List[dict]: ...

    @abc.abstractmethod
    def get_global_traffic_stats(self, hours: int = 24) -> dict: ...


class IAuditRepository(abc.ABC):
    """Repository for security audit log entries."""

    @abc.abstractmethod
    def insert_audit_log(
        self,
        event_type: str,
        message: str,
        app_name: Optional[str] = None,
        port: Optional[int] = None,
        pid: Optional[int] = None,
        severity: str = "info",
        details: Optional[str] = None,
    ) -> None: ...

    @abc.abstractmethod
    def get_audit_logs(self, limit: int = 100) -> List[dict]: ...


class IApprovalRepository(abc.ABC):
    """Repository for analyst approval workflow records."""

    @abc.abstractmethod
    def create_analyst_approval(
        self,
        action_type: str,
        target_identifier: str,
        reason: str,
        risk_score: int = 0,
    ) -> int: ...

    @abc.abstractmethod
    def update_approval_status(
        self, approval_id: int, status: str, resolved_by: str
    ) -> bool: ...

    @abc.abstractmethod
    def get_pending_approvals(self) -> List[dict]: ...


class IThreatRepository(abc.ABC):
    """Repository for threat intelligence data persistence."""

    @abc.abstractmethod
    def get_malicious_ips(self) -> set: ...

    @abc.abstractmethod
    def update_malicious_ips(self, ips: set) -> None: ...


class IRuleRepository(abc.ABC):
    """Repository for policy rule persistence."""

    @abc.abstractmethod
    def get_rules(self) -> List[dict]: ...

    @abc.abstractmethod
    def save_rule(self, rule: dict) -> None: ...

    @abc.abstractmethod
    def delete_rule(self, rule_id: str) -> bool: ...


class IConfigRepository(abc.ABC):
    """Repository for application configuration key-value pairs."""

    @abc.abstractmethod
    def set_config(self, key: str, value: str) -> None: ...

    @abc.abstractmethod
    def get_config(
        self, key: str, default: Optional[str] = None
    ) -> Optional[str]: ...


class IPreferenceRepository(abc.ABC):
    """Repository for user preferences."""

    @abc.abstractmethod
    def set_user_preference(self, key: str, value: str) -> None: ...

    @abc.abstractmethod
    def get_user_preferences(self) -> Dict[str, str]: ...


class IDashboardRepository(abc.ABC):
    """Repository for dashboard layout persistence."""

    @abc.abstractmethod
    def save_dashboard_layout(
        self, user_id: int, layout_json: str, name: str = "default"
    ) -> None: ...

    @abc.abstractmethod
    def get_dashboard_layout(
        self, name: str = "default"
    ) -> Optional[str]: ...
