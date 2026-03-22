"""
Sentinel Database Layer — SQLite + InfluxDB + Supabase.

SQLite:  Local config cache, process-name map, 24h traffic history
InfluxDB: Time-series traffic ingestion for historical "Top Usage" queries
Supabase: User accounts + blocked-port-list sync across devices
"""

import os
import time
import sqlite3
import logging
import asyncio
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any

logger = logging.getLogger("sentinel.db")

# --- SQLite ---

DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "sentinel.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS traffic_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    port INTEGER NOT NULL,
    pid INTEGER NOT NULL,
    app_name TEXT NOT NULL DEFAULT 'Unknown',
    kb_s_in REAL NOT NULL DEFAULT 0.0,
    kb_s_out REAL NOT NULL DEFAULT 0.0,
    protocol TEXT NOT NULL DEFAULT 'TCP',
    direction TEXT NOT NULL DEFAULT 'both',
    risk_score INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_traffic_timestamp ON traffic_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_traffic_port ON traffic_history(port);

CREATE TABLE IF NOT EXISTS process_map (
    pid INTEGER PRIMARY KEY,
    app_name TEXT NOT NULL,
    first_seen REAL NOT NULL,
    last_seen REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS config_cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS blocked_ports (
    port INTEGER PRIMARY KEY,
    block_type TEXT NOT NULL DEFAULT 'hard',
    blocked_at REAL NOT NULL,
    reason TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp REAL NOT NULL,
    event_type TEXT NOT NULL, -- 'policy_trigger', 'manual_block', 'process_kill'
    app_name TEXT,
    port INTEGER,
    pid INTEGER,
    severity TEXT NOT NULL DEFAULT 'info', -- 'info', 'warning', 'critical'
    message TEXT NOT NULL,
    details TEXT -- JSON or string
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_logs(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_logs(event_type);
"""


class SQLiteDB:
    """Local SQLite database for config, process map, and traffic history."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or DEFAULT_DB_PATH)
        # Ensure data directory exists
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._write_lock = threading.Lock()

    def connect(self) -> None:
        """Initialize the database connection and schema."""
        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=10.0,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._conn.execute("PRAGMA busy_timeout=5000;")
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()
        
        # --- Safe Migration ---
        # Ensure risk_score column exists if the table was created by an older version
        try:
            self._conn.execute("ALTER TABLE traffic_history ADD COLUMN risk_score INTEGER DEFAULT 0;")
            self._conn.commit()
            logger.info("Migrated database: added risk_score column")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e).lower():
                logger.warning(f"Migration notice: {e}")
        
        logger.info(f"SQLite connected: {self.db_path}")

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.connect()
        return self._conn

    # --- Traffic History ---

    def insert_traffic(self, records: List[Dict[str, Any]]) -> None:
        """Batch insert traffic records."""
        if not records:
            return

        normalized_records = []
        for record in records:
            normalized_records.append(
                {
                    "timestamp": float(record.get("timestamp", time.time())),
                    "port": int(record.get("port", 0)),
                    "pid": int(record.get("pid", 0)),
                    "app_name": str(record.get("app_name", "Unknown")),
                    "kb_s_in": float(record.get("kb_s_in", 0.0)),
                    "kb_s_out": float(record.get("kb_s_out", 0.0)),
                    "protocol": str(record.get("protocol", "TCP")),
                    "direction": str(record.get("direction", "both")),
                    "risk_score": int(record.get("risk_score", 0)),
                }
            )

        with self._write_lock:
            self.conn.executemany(
                """INSERT INTO traffic_history
                   (timestamp, port, pid, app_name, kb_s_in, kb_s_out, protocol, direction, risk_score)
                   VALUES (:timestamp, :port, :pid, :app_name, :kb_s_in, :kb_s_out, :protocol, :direction, :risk_score)""",
                normalized_records,
            )
            self.conn.commit()

    def get_traffic_history(self, port: int, hours: int = 24) -> List[dict]:
        """Get traffic history for a port within the last N hours."""
        cutoff = time.time() - (hours * 3600)
        cursor = self.conn.execute(
            "SELECT * FROM traffic_history WHERE port = ? AND timestamp >= ? ORDER BY timestamp",
            (port, cutoff),
        )
        return [dict(row) for row in cursor.fetchall()]

    def prune_old_traffic(self, max_age_hours: int = 24) -> int:
        """Delete traffic records older than max_age_hours."""
        cutoff = time.time() - (max_age_hours * 3600)
        cursor = self.conn.execute(
            "DELETE FROM traffic_history WHERE timestamp < ?", (cutoff,)
        )
        self.conn.commit()
        return cursor.rowcount

    # --- Process Map ---

    def upsert_process(self, pid: int, app_name: str) -> None:
        """Insert or update process map entry."""
        now = time.time()
        self.conn.execute(
            """INSERT INTO process_map (pid, app_name, first_seen, last_seen)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(pid) DO UPDATE SET app_name=?, last_seen=?""",
            (pid, app_name, now, now, app_name, now),
        )
        self.conn.commit()

    def get_process_name(self, pid: int) -> Optional[str]:
        """Look up app name by PID."""
        cursor = self.conn.execute(
            "SELECT app_name FROM process_map WHERE pid = ?", (pid,)
        )
        row = cursor.fetchone()
        return row["app_name"] if row else None

    # --- Config Cache ---

    def set_config(self, key: str, value: str) -> None:
        """Set a config value."""
        self.conn.execute(
            """INSERT INTO config_cache (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value=?, updated_at=?""",
            (key, value, time.time(), value, time.time()),
        )
        self.conn.commit()

    def get_config(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a config value."""
        cursor = self.conn.execute(
            "SELECT value FROM config_cache WHERE key = ?", (key,)
        )
        row = cursor.fetchone()
        return row["value"] if row else default

    # --- Blocked Ports ---

    def add_blocked_port(self, port: int, block_type: str = "hard", reason: str = "") -> None:
        """Record a blocked port."""
        self.conn.execute(
            """INSERT OR REPLACE INTO blocked_ports (port, block_type, blocked_at, reason)
               VALUES (?, ?, ?, ?)""",
            (port, block_type, time.time(), reason),
        )
        self.conn.commit()

    def remove_blocked_port(self, port: int) -> None:
        """Remove a blocked port record."""
        self.conn.execute("DELETE FROM blocked_ports WHERE port = ?", (port,))
        self.conn.commit()

    def get_blocked_ports(self) -> List[dict]:
        """Get all currently blocked ports."""
        cursor = self.conn.execute("SELECT * FROM blocked_ports ORDER BY port")
        return [dict(row) for row in cursor.fetchall()]

    def clear_blocked_ports(self) -> int:
        """Remove all blocked port records."""
        cursor = self.conn.execute("DELETE FROM blocked_ports")
        self.conn.commit()
        return cursor.rowcount

    # --- Audit Logs ---

    def insert_audit_log(self, event_type: str, message: str, app_name: Optional[str] = None, 
                         port: Optional[int] = None, pid: Optional[int] = None, 
                         severity: str = "info", details: Optional[str] = None) -> None:
        """Record a system or security event."""
        self.conn.execute(
            """INSERT INTO audit_logs 
               (timestamp, event_type, app_name, port, pid, severity, message, details)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (time.time(), event_type, app_name, port, pid, severity, message, details),
        )
        self.conn.commit()

    def get_audit_logs(self, limit: int = 100) -> List[dict]:
        """Get recent audit logs."""
        cursor = self.conn.execute(
            "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]

    # --- Analytics & Forensics ---

    def get_top_talkers(self, hours: int = 24, limit: int = 10) -> List[dict]:
        """
        Identify applications with the highest cumulative traffic.
        Returns total bytes transferred (KB) per application.
        """
        cutoff = time.time() - (hours * 3600)
        # We sum KB/s snapshots (at ~1Hz) to estimate total KB
        cursor = self.conn.execute(
            """SELECT app_name, SUM(kb_s_in + kb_s_out) as total_kb, 
                      MAX(risk_score) as max_risk
               FROM traffic_history 
               WHERE timestamp >= ? 
               GROUP BY app_name 
               ORDER BY total_kb DESC 
               LIMIT ?""",
            (cutoff, limit),
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_global_traffic_stats(self, hours: int = 24) -> dict:
        """Get aggregated traffic volume across the whole system."""
        cutoff = time.time() - (hours * 3600)
        cursor = self.conn.execute(
            """SELECT SUM(kb_s_in) as total_in_kb, SUM(kb_s_out) as total_out_kb
               FROM traffic_history WHERE timestamp >= ?""",
            (cutoff,),
        )
        row = cursor.fetchone()
        return {
            "total_in_mb": round((row["total_in_kb"] or 0) / 1024, 2),
            "total_out_mb": round((row["total_out_kb"] or 0) / 1024, 2),
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
        """Initialize InfluxDB client. Returns True if connected."""
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
        """Write traffic data points to InfluxDB."""
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
        """Close the InfluxDB client."""
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
        """Initialize Supabase client. Returns True if connected."""
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
        """Sign in a user."""
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
        """Register a new user."""
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
        """Upload blocked port list to Supabase for cross-device sync."""
        if not self._client:
            return False
        try:
            # Upsert blocked ports for this user
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
        """Fetch blocked port list from Supabase."""
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
        """Close Supabase client."""
        self._client = None
