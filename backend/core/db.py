"""
Sentinel Database Layer — SQLAlchemy ORM + InfluxDB + Supabase.

SQLAlchemy: Local config cache, process-name map, 24h traffic history, approvals
InfluxDB: Time-series traffic ingestion for historical "Top Usage" queries
Supabase: User accounts + blocked-port-list sync across devices
"""

import os
import time
import logging
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

from sqlalchemy import create_engine, func, event
from sqlalchemy.orm import sessionmaker, Session

from backend.core.models import (
    Base, TrafficHistory, ProcessMap, ConfigCache, BlockedPort, 
    AuditLog, AnalystApproval, ApprovalStatus, ActionType
)

logger = logging.getLogger("sentinel.db")

# --- SQLAlchemy ---

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "sentinel.db"

class SQLiteDB:
    """Local SQLite database utilizing SQLAlchemy ORM."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.engine = None
        self.SessionLocal = None
        self._write_lock = threading.Lock()

    def connect(self) -> None:
        """Initialize the SQLAlchemy engine and session factory."""
        db_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(
            db_url,
            connect_args={"check_same_thread": False, "timeout": 10.0},
        )
        
        # PRAGMA commands for SQLite performance
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        logger.info(f"SQLAlchemy connected: {db_url}")

    def close(self) -> None:
        """Dispose the database engine."""
        if self.engine:
            self.engine.dispose()
            self.engine = None

    def get_session(self) -> Session:
        if self.SessionLocal is None:
            self.connect()
        return self.SessionLocal()

    # --- Traffic History ---

    def insert_traffic(self, records: List[Dict[str, Any]]) -> None:
        if not records:
            return

        traffic_objs = [
            TrafficHistory(
                timestamp=float(r.get("timestamp", time.time())),
                port=int(r.get("port", 0)),
                pid=int(r.get("pid", 0)),
                app_name=str(r.get("app_name", "Unknown")),
                kb_s_in=float(r.get("kb_s_in", 0.0)),
                kb_s_out=float(r.get("kb_s_out", 0.0)),
                protocol=str(r.get("protocol", "TCP")),
                direction=str(r.get("direction", "both")),
                risk_score=int(r.get("risk_score", 0)),
            ) for r in records
        ]

        with self._write_lock:
            with self.get_session() as session:
                session.bulk_save_objects(traffic_objs)
                session.commit()

    def get_traffic_history(self, port: int, hours: int = 24) -> List[dict]:
        cutoff = time.time() - (hours * 3600)
        with self.get_session() as session:
            records = session.query(TrafficHistory).filter(
                TrafficHistory.port == port,
                TrafficHistory.timestamp >= cutoff
            ).order_by(TrafficHistory.timestamp).all()
            return [
                {
                    "id": r.id, "timestamp": r.timestamp, "port": r.port, "pid": r.pid,
                    "app_name": r.app_name, "kb_s_in": r.kb_s_in, "kb_s_out": r.kb_s_out,
                    "protocol": r.protocol, "direction": r.direction, "risk_score": r.risk_score
                } for r in records
            ]

    def prune_old_traffic(self, max_age_hours: int = 24) -> int:
        cutoff = time.time() - (max_age_hours * 3600)
        with self._write_lock:
            with self.get_session() as session:
                deleted_count = session.query(TrafficHistory).filter(TrafficHistory.timestamp < cutoff).delete()
                session.commit()
                return deleted_count

    # --- Process Map ---

    def upsert_process(self, pid: int, app_name: str) -> None:
        now = time.time()
        with self._write_lock:
            with self.get_session() as session:
                proc = session.query(ProcessMap).filter(ProcessMap.pid == pid).first()
                if proc:
                    proc.app_name = app_name
                    proc.last_seen = now
                else:
                    proc = ProcessMap(pid=pid, app_name=app_name, first_seen=now, last_seen=now)
                    session.add(proc)
                session.commit()

    def get_process_name(self, pid: int) -> Optional[str]:
        with self.get_session() as session:
            proc = session.query(ProcessMap).filter(ProcessMap.pid == pid).first()
            return proc.app_name if proc else None

    # --- Config Cache ---

    def set_config(self, key: str, value: str) -> None:
        with self._write_lock:
            with self.get_session() as session:
                conf = session.query(ConfigCache).filter(ConfigCache.key == key).first()
                if conf:
                    conf.value = value
                    conf.updated_at = time.time()
                else:
                    conf = ConfigCache(key=key, value=value, updated_at=time.time())
                    session.add(conf)
                session.commit()

    def get_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self.get_session() as session:
            conf = session.query(ConfigCache).filter(ConfigCache.key == key).first()
            return conf.value if conf else default

    # --- Blocked Ports ---

    def add_blocked_port(self, port: int, block_type: str = "hard", reason: str = "") -> None:
        with self._write_lock:
            with self.get_session() as session:
                bp = session.query(BlockedPort).filter(BlockedPort.port == port).first()
                if bp:
                    bp.block_type = block_type
                    bp.blocked_at = time.time()
                    bp.reason = reason
                else:
                    bp = BlockedPort(port=port, block_type=block_type, blocked_at=time.time(), reason=reason)
                    session.add(bp)
                session.commit()

    def remove_blocked_port(self, port: int) -> None:
        with self._write_lock:
            with self.get_session() as session:
                session.query(BlockedPort).filter(BlockedPort.port == port).delete()
                session.commit()

    def get_blocked_ports(self) -> List[dict]:
        with self.get_session() as session:
            records = session.query(BlockedPort).order_by(BlockedPort.port).all()
            return [
                {
                    "port": r.port, "block_type": r.block_type,
                    "blocked_at": r.blocked_at, "reason": r.reason
                } for r in records
            ]

    def clear_blocked_ports(self) -> int:
        with self._write_lock:
            with self.get_session() as session:
                deleted_count = session.query(BlockedPort).delete()
                session.commit()
                return deleted_count

    # --- Audit Logs ---

    def insert_audit_log(self, event_type: str, message: str, app_name: Optional[str] = None, 
                         port: Optional[int] = None, pid: Optional[int] = None, 
                         severity: str = "info", details: Optional[str] = None) -> None:
        with self._write_lock:
            with self.get_session() as session:
                log = AuditLog(
                    timestamp=time.time(), event_type=event_type,
                    app_name=app_name, port=port, pid=pid,
                    severity=severity, message=message, details=details
                )
                session.add(log)
                session.commit()

    def get_audit_logs(self, limit: int = 100) -> List[dict]:
        with self.get_session() as session:
            records = session.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
            return [
                {
                    "id": r.id, "timestamp": r.timestamp, "event_type": r.event_type,
                    "app_name": r.app_name, "port": r.port, "pid": r.pid,
                    "severity": r.severity, "message": r.message, "details": r.details
                } for r in records
            ]

    # --- Analyst Approvals ---

    def create_analyst_approval(self, action_type: str, target_identifier: str, reason: str, risk_score: int = 0) -> int:
        """Create a new approval request."""
        with self._write_lock:
            with self.get_session() as session:
                approval = AnalystApproval(
                    action_type=action_type,
                    target_identifier=target_identifier,
                    reason=reason,
                    risk_score=risk_score
                )
                session.add(approval)
                session.commit()
                return approval.id

    def update_approval_status(self, approval_id: int, status: str, resolved_by: str) -> bool:
        """Update the status of an approval request."""
        with self._write_lock:
            with self.get_session() as session:
                approval = session.query(AnalystApproval).filter(AnalystApproval.id == approval_id).first()
                if not approval:
                    return False
                approval.status = status
                approval.resolved_by = resolved_by
                approval.resolved_at = time.time()
                session.commit()
                return True

    def get_pending_approvals(self) -> List[dict]:
        """Get all pending analyst approvals."""
        with self.get_session() as session:
            records = session.query(AnalystApproval).filter(AnalystApproval.status == ApprovalStatus.PENDING.value).order_by(AnalystApproval.risk_score.desc()).all()
            return [
                {
                    "id": r.id, "created_at": r.created_at, "action_type": r.action_type,
                    "target_identifier": r.target_identifier, "reason": r.reason,
                    "status": r.status, "risk_score": r.risk_score
                } for r in records
            ]

    # --- Analytics & Forensics ---

    def get_top_talkers(self, hours: int = 24, limit: int = 10) -> List[dict]:
        cutoff = time.time() - (hours * 3600)
        with self.get_session() as session:
            records = session.query(
                TrafficHistory.app_name,
                func.sum(TrafficHistory.kb_s_in + TrafficHistory.kb_s_out).label("total_kb"),
                func.max(TrafficHistory.risk_score).label("max_risk")
            ).filter(TrafficHistory.timestamp >= cutoff).group_by(TrafficHistory.app_name).order_by(
                func.sum(TrafficHistory.kb_s_in + TrafficHistory.kb_s_out).desc()
            ).limit(limit).all()
            
            return [
                {"app_name": r.app_name, "total_kb": r.total_kb, "max_risk": r.max_risk}
                for r in records
            ]

    def get_global_traffic_stats(self, hours: int = 24) -> dict:
        cutoff = time.time() - (hours * 3600)
        with self.get_session() as session:
            stats = session.query(
                func.sum(TrafficHistory.kb_s_in).label("total_in_kb"),
                func.sum(TrafficHistory.kb_s_out).label("total_out_kb")
            ).filter(TrafficHistory.timestamp >= cutoff).first()

            return {
                "total_in_mb": round((stats.total_in_kb or 0) / 1024, 2),
                "total_out_mb": round((stats.total_out_kb or 0) / 1024, 2),
            }


# --- InfluxDB ---

class InfluxDBWriter:
    """
    InfluxDB time-series writer for traffic data.

    Uses the influxdb-client library for InfluxDB 2.x.
    Falls back gracefully if InfluxDB is not configured.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        org: Optional[str] = None,
        bucket: Optional[str] = None,
    ):
        self.url = url or os.environ.get("INFLUXDB_URL", "http://localhost:8086")
        self.token = token or os.environ.get("INFLUXDB_TOKEN", "")
        self.org = org or os.environ.get("INFLUXDB_ORG", "sentinel")
        self.bucket = bucket or os.environ.get("INFLUXDB_BUCKET", "traffic")
        self._client = None
        self._write_api = None

    def connect(self) -> bool:
        if not self.token:
            logger.warning("InfluxDB token not configured; time-series writes disabled")
            return False
        try:
            from influxdb_client import InfluxDBClient
            from influxdb_client.client.write_api import SYNCHRONOUS

            self._client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
            self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
            logger.info(f"InfluxDB connected: {self.url}/{self.bucket}")
            return True
        except Exception as e:
            logger.warning(f"InfluxDB connection failed: {e}")
            return False

    def write_traffic(self, records: List[Dict[str, Any]]) -> None:
        if self._write_api is None:
            return
        try:
            from influxdb_client import Point

            points = []
            for r in records:
                point = (
                    Point("traffic")
                    .tag("port", str(r["port"]))
                    .tag("app_name", r.get("app_name", "Unknown"))
                    .tag("protocol", r.get("protocol", "TCP"))
                    .field("kb_s_in", float(r.get("kb_s_in", 0.0)))
                    .field("kb_s_out", float(r.get("kb_s_out", 0.0)))
                    .field("pid", int(r.get("pid", 0)))
                    .field("risk_score", int(r.get("risk_score", 0)))
                    .time(int(r.get("timestamp", time.time()) * 1e9))  # nanoseconds
                )
                points.append(point)

            self._write_api.write(bucket=self.bucket, record=points)
        except Exception as e:
            logger.debug(f"InfluxDB write error: {e}")

    def close(self) -> None:
        if self._client:
            self._client.close()
            self._client = None
            self._write_api = None


# --- Supabase ---

class SupabaseSync:
    """
    Supabase client for auth + blocked-port-list sync across devices.

    Falls back gracefully if Supabase is not configured.
    """

    def __init__(
        self,
        url: str = "",
        key: str = "",
    ):
        self.url = url or os.environ.get("SUPABASE_URL", "")
        self.key = key or os.environ.get("SUPABASE_KEY", "")
        self._client = None

    def connect(self) -> bool:
        if not self.url or not self.key:
            logger.warning("Supabase not configured; cloud sync disabled")
            return False
        try:
            from supabase import create_client

            self._client = create_client(self.url, self.key)
            logger.info(f"Supabase connected: {self.url}")
            return True
        except Exception as e:
            logger.warning(f"Supabase connection failed: {e}")
            return False

    def sign_in(self, email: str, password: str) -> Optional[dict]:
        if not self._client:
            return None
        try:
            response = self._client.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
            return {"user": response.user.id, "session": response.session.access_token}
        except Exception as e:
            logger.error(f"Supabase sign-in failed: {e}")
            return None

    def sign_up(self, email: str, password: str) -> Optional[dict]:
        if not self._client:
            return None
        try:
            response = self._client.auth.sign_up(
                {"email": email, "password": password}
            )
            return {"user": response.user.id}
        except Exception as e:
            logger.error(f"Supabase sign-up failed: {e}")
            return None

    def sync_blocked_ports(self, user_id: str, blocked_ports: List[dict]) -> bool:
        if not self._client:
            return False
        try:
            for bp in blocked_ports:
                self._client.table("blocked_ports").upsert({
                    "user_id": user_id,
                    "port": bp["port"],
                    "block_type": bp.get("block_type", "hard"),
                    "blocked_at": bp.get("blocked_at", time.time()),
                    "reason": bp.get("reason", ""),
                }).execute()
            return True
        except Exception as e:
            logger.error(f"Supabase sync failed: {e}")
            return False

    def fetch_blocked_ports(self, user_id: str) -> List[dict]:
        if not self._client:
            return []
        try:
            response = (
                self._client.table("blocked_ports")
                .select("*")
                .eq("user_id", user_id)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Supabase fetch failed: {e}")
            return []

    def close(self) -> None:
        self._client = None
