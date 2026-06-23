import enum
import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Enum, ForeignKey
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class TrafficHistory(Base):
    __tablename__ = "traffic_history"
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(Float, nullable=False, index=True)
    port = Column(Integer, nullable=False, index=True)
    pid = Column(Integer, nullable=False)
    app_name = Column(String, nullable=False, default="Unknown")
    kb_s_in = Column(Float, nullable=False, default=0.0)
    kb_s_out = Column(Float, nullable=False, default=0.0)
    protocol = Column(String, nullable=False, default="TCP")
    direction = Column(String, nullable=False, default="both")
    risk_score = Column(Integer, default=0)


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
    severity = Column(String, nullable=False, default="info")
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
    created_at = Column(Float, nullable=False, default=lambda: datetime.datetime.now().timestamp())
    action_type = Column(String, nullable=False)  # Map to ActionType enum values
    target_identifier = Column(String, nullable=False) # e.g., '443' for port, '1204' for pid
    reason = Column(String, nullable=False)
    status = Column(String, nullable=False, default=ApprovalStatus.PENDING.value)
    risk_score = Column(Integer, default=0)
    resolved_at = Column(Float, nullable=True)
    resolved_by = Column(String, nullable=True) # E.g., 'admin_user_id'


class RoleEnum(str, enum.Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False, default=RoleEnum.VIEWER.value)
    is_active = Column(Boolean, default=True)
    created_at = Column(Float, nullable=False, default=lambda: datetime.datetime.now().timestamp())
