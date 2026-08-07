"""
Infrastructure Database — SQLite repository implementation.

Implements all domain repository interfaces, providing a unified
database access layer. This is the only file that imports SQLAlchemy.

Re-exports the existing SQLiteDB class from core/db.py with compatibility
wrappers to implement the new repository interfaces.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.core.db import SQLiteDB as _SQLiteDB
from backend.domain.interfaces.repositories import (
    IApprovalRepository,
    IAuditRepository,
    IConfigRepository,
    IDashboardRepository,
    IHistoryRepository,
    IPortRepository,
    IPreferenceRepository,
)

logger = logging.getLogger("vigilant.infrastructure.database")


class DatabaseRepository(
    IPortRepository,
    IHistoryRepository,
    IAuditRepository,
    IApprovalRepository,
    IConfigRepository,
    IPreferenceRepository,
    IDashboardRepository,
):
    """
    Unified database repository implementing all domain interfaces.

    Wraps the existing SQLiteDB class to maintain backward compatibility
    while fulfilling the new Clean Architecture contracts.
    """

    def __init__(self, db_url: str = "sqlite:///vigilant_data.db") -> None:
        self._db = _SQLiteDB(db_url=db_url)
        logger.info("Database repository initialized (%s)", db_url.split("///")[0])

    # --- Direct pass-through properties ---

    @property
    def engine(self) -> Any:
        return self._db.engine

    @property
    def session_factory(self) -> Any:
        return self._db.session_factory

    # --- IPortRepository ---

    def add_blocked_port(
        self, port: int, block_type: str = "hard", reason: str = ""
    ) -> None:
        self._db.add_blocked_port(port, block_type, reason)

    def remove_blocked_port(self, port: int) -> None:
        self._db.remove_blocked_port(port)

    def get_blocked_ports(self) -> List[dict]:
        return self._db.get_blocked_ports()

    def clear_blocked_ports(self) -> int:
        return self._db.clear_blocked_ports()

    # --- IHistoryRepository ---

    def insert_traffic(self, records: List[Dict[str, Any]]) -> None:
        self._db.insert_traffic(records)

    def get_traffic_history(self, port: int, hours: int = 24) -> List[dict]:
        return self._db.get_traffic_history(port, hours)

    def prune_old_traffic(self, max_age_hours: int = 24) -> int:
        return self._db.prune_old_traffic(max_age_hours)

    def get_top_talkers(
        self, hours: int = 24, limit: int = 10
    ) -> List[dict]:
        return self._db.get_top_talkers(hours, limit)

    def get_global_traffic_stats(self, hours: int = 24) -> dict:
        return self._db.get_global_traffic_stats(hours)

    # --- IAuditRepository ---

    def insert_audit_log(
        self,
        event_type: str,
        message: str,
        app_name: Optional[str] = None,
        port: Optional[int] = None,
        pid: Optional[int] = None,
        severity: str = "info",
        details: Optional[str] = None,
    ) -> None:
        self._db.insert_audit_log(
            event_type, message, app_name, port, pid, severity, details
        )

    def get_audit_logs(self, limit: int = 100) -> List[dict]:
        return self._db.get_audit_logs(limit)

    # --- IApprovalRepository ---

    def create_analyst_approval(
        self,
        action_type: str,
        target_identifier: str,
        reason: str,
        risk_score: int = 0,
    ) -> int:
        return self._db.create_analyst_approval(
            action_type, target_identifier, reason, risk_score
        )

    def update_approval_status(
        self, approval_id: int, status: str, resolved_by: str
    ) -> bool:
        return self._db.update_approval_status(
            approval_id, status, resolved_by
        )

    def get_pending_approvals(self) -> List[dict]:
        return self._db.get_pending_approvals()

    # --- IConfigRepository ---

    def set_config(self, key: str, value: str) -> None:
        self._db.set_config(key, value)

    def get_config(
        self, key: str, default: Optional[str] = None
    ) -> Optional[str]:
        return self._db.get_config(key, default)

    # --- IPreferenceRepository ---

    def set_user_preference(self, key: str, value: str) -> None:
        self._db.set_user_preference(key, value)

    def get_user_preferences(self) -> Dict[str, str]:
        return self._db.get_user_preferences()

    # --- IDashboardRepository ---

    def save_dashboard_layout(
        self, user_id: int, layout_json: str, name: str = "default"
    ) -> None:
        self._db.save_dashboard_layout(user_id, layout_json, name)

    def get_dashboard_layout(
        self, name: str = "default"
    ) -> Optional[str]:
        return self._db.get_dashboard_layout(name)

    # --- Lifecycle ---

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._db, "engine"):
            self._db.engine.dispose()
