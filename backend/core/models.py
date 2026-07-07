"""
Vigilant Database Models — SQLAlchemy ORM definitions.

All tables are auto-created on first startup via Base.metadata.create_all().
"""

import enum
import datetime
import time
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, Index, ForeignKey,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ProcessMap(Base):
    __tablename__ = "process_map"

    pid = Column(Integer, primary_key=True)
    app_name = Column(String, nullable=False)
    first_seen = Column(Float, nullable=False)
    last_seen = Column(Float, nullable=False)


class ConfigCache(Base):
    __tablename__ = "config_cache"

    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)
    updated_at = Column(Float, nullable=False)


class BlockedPort(Base):
    __tablename__ = "blocked_ports"

    port = Column(Integer, primary_key=True)
    block_type = Column(String, nullable=False, default="hard")
    blocked_at = Column(Float, nullable=False)
    reason = Column(String, default="")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(Float, nullable=False, index=True)
    event_type = Column(String, nullable=False, index=True)
    app_name = Column(String)
    port = Column(Integer)
    pid = Column(Integer)
    severity = Column(String, nullable=False, default="info", index=True)
    message = Column(String, nullable=False)
    details = Column(String)


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ActionType(str, enum.Enum):
    BLOCK_PORT = "block_port"
    SUSPEND_PROCESS = "suspend_process"
    ISOLATE_NETWORK = "isolate_network"


class AnalystApproval(Base):
    __tablename__ = "analyst_approvals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(Float, nullable=False, default=time.time)
    action_type = Column(String, nullable=False)
    target_identifier = Column(String, nullable=False)
    reason = Column(String, nullable=False)
    status = Column(String, nullable=False, default=ApprovalStatus.PENDING.value, index=True)
    risk_score = Column(Integer, default=0)
    resolved_at = Column(Float, nullable=True)
    resolved_by = Column(String, nullable=True)


class UserPreference(Base):
    """Key-value application preferences (theme, refresh interval, alert thresholds)."""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String, nullable=False, unique=True)
    value = Column(String, nullable=False)



