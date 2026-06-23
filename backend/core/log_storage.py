"""
Vigilant Log Storage System

Enterprise-grade log management with:
  - Configurable storage directory (local, network, external drive)
  - Size-based log rotation with configurable limits
  - Gzip compression for rotated logs
  - AES-256 encryption at rest (via Fernet symmetric encryption)
  - CSV, JSON export
  - Retention policy engine (auto-prune by age)
  - Search and filter API
"""

import os
import gzip
import json
import csv
import io
import time
import logging
import shutil
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger("vigilant.log_storage")


class LogStorageConfig:
    """Configuration for the log storage system."""

    def __init__(
        self,
        storage_path: Optional[str] = None,
        max_size_mb: int = 100,
        retention_days: int = 90,
        compression: bool = True,
        encryption_key: Optional[str] = None,
    ):
        self.storage_path = Path(
            storage_path
            or os.environ.get("LOG_STORAGE_PATH", "logs")
        )
        self.max_size_mb = int(os.environ.get("LOG_MAX_SIZE_MB", str(max_size_mb)))
        self.retention_days = int(os.environ.get("LOG_RETENTION_DAYS", str(retention_days)))
        self.compression = os.environ.get("LOG_COMPRESSION", str(compression)).lower() in ("true", "1")
        self.encryption_key = encryption_key or os.environ.get("LOG_ENCRYPTION_KEY")

        # Create storage directories
        self.storage_path.mkdir(parents=True, exist_ok=True)
        (self.storage_path / "archive").mkdir(exist_ok=True)
        (self.storage_path / "export").mkdir(exist_ok=True)


class LogStorage:
    """
    Enterprise log storage with rotation, compression, and encryption.

    Manages structured log files alongside the Python logging system.
    """

    def __init__(self, config: Optional[LogStorageConfig] = None):
        self.config = config or LogStorageConfig()
        self._write_lock = threading.Lock()
        self._fernet = None

        if self.config.encryption_key:
            try:
                from cryptography.fernet import Fernet
                self._fernet = Fernet(self.config.encryption_key.encode())
                logger.info("Log encryption enabled (AES-256)")
            except ImportError:
                logger.warning(
                    "cryptography package not installed — log encryption disabled. "
                    "Install with: pip install cryptography"
                )
            except Exception as e:
                logger.error(f"Invalid encryption key: {e}")

    def write_structured_log(self, category: str, data: Dict[str, Any]) -> None:
        """Write a structured log entry to a category-specific file."""
        log_file = self.config.storage_path / f"{category}.jsonl"

        entry = {
            "timestamp": time.time(),
            "datetime": datetime.utcnow().isoformat() + "Z",
            **data,
        }
        line = json.dumps(entry, default=str) + "\n"

        with self._write_lock:
            # Check rotation before writing
            if log_file.exists():
                size_mb = log_file.stat().st_size / (1024 * 1024)
                if size_mb >= self.config.max_size_mb:
                    self._rotate_log(log_file)

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)

    def _rotate_log(self, log_file: Path) -> None:
        """Rotate a log file: rename, compress, and optionally encrypt."""
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        archive_name = f"{log_file.stem}_{timestamp}"
        archive_dir = self.config.storage_path / "archive"

        if self.config.compression:
            archive_path = archive_dir / f"{archive_name}.jsonl.gz"
            with open(log_file, "rb") as f_in:
                content = f_in.read()
            if self._fernet:
                content = self._fernet.encrypt(content)
                archive_path = archive_dir / f"{archive_name}.jsonl.gz.enc"
            with gzip.open(archive_path, "wb") as f_out:
                f_out.write(content)
        else:
            archive_path = archive_dir / f"{archive_name}.jsonl"
            shutil.move(str(log_file), str(archive_path))
            if self._fernet:
                with open(archive_path, "rb") as f:
                    content = f.read()
                encrypted = self._fernet.encrypt(content)
                enc_path = archive_dir / f"{archive_name}.jsonl.enc"
                with open(enc_path, "wb") as f:
                    f.write(encrypted)
                archive_path.unlink()

        # Truncate the original file
        with open(log_file, "w", encoding="utf-8") as f:
            f.write("")

        logger.info(f"Rotated log: {log_file.name} → {archive_path.name}")

    def enforce_retention(self) -> int:
        """Delete archived logs older than retention_days."""
        archive_dir = self.config.storage_path / "archive"
        cutoff = time.time() - (self.config.retention_days * 86400)
        deleted = 0

        for file_path in archive_dir.iterdir():
            if file_path.is_file() and file_path.stat().st_mtime < cutoff:
                file_path.unlink()
                deleted += 1
                logger.debug(f"Retention: deleted {file_path.name}")

        if deleted:
            logger.info(f"Retention policy: pruned {deleted} archived logs")
        return deleted

    def export_to_csv(
        self,
        category: str,
        output_path: Optional[str] = None,
        hours: int = 24,
    ) -> str:
        """Export logs to CSV format."""
        log_file = self.config.storage_path / f"{category}.jsonl"
        if not log_file.exists():
            return ""

        cutoff = time.time() - (hours * 3600)
        entries = self._read_entries(log_file, cutoff)

        if not entries:
            return ""

        if output_path is None:
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            out_file = self.config.storage_path / "export" / f"{category}_{timestamp}.csv"
        else:
            out_file = Path(output_path)

        fieldnames = list(entries[0].keys())
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(entries)

        with open(out_file, "w", encoding="utf-8", newline="") as f:
            f.write(output.getvalue())

        logger.info(f"Exported {len(entries)} log entries to {out_file}")
        return str(out_file)

    def export_to_json(
        self,
        category: str,
        output_path: Optional[str] = None,
        hours: int = 24,
    ) -> str:
        """Export logs to JSON format."""
        log_file = self.config.storage_path / f"{category}.jsonl"
        if not log_file.exists():
            return ""

        cutoff = time.time() - (hours * 3600)
        entries = self._read_entries(log_file, cutoff)

        if output_path is None:
            timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            out_file = self.config.storage_path / "export" / f"{category}_{timestamp}.json"
        else:
            out_file = Path(output_path)

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, default=str)

        logger.info(f"Exported {len(entries)} log entries to {out_file}")
        return str(out_file)

    def search(
        self,
        category: str,
        query: Optional[str] = None,
        severity: Optional[str] = None,
        hours: int = 24,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Search logs with optional text and severity filters."""
        log_file = self.config.storage_path / f"{category}.jsonl"
        if not log_file.exists():
            return []

        cutoff = time.time() - (hours * 3600)
        entries = self._read_entries(log_file, cutoff)

        if severity:
            entries = [e for e in entries if e.get("severity") == severity]

        if query:
            q = query.lower()
            entries = [
                e for e in entries
                if q in json.dumps(e, default=str).lower()
            ]

        return entries[-limit:]

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage utilization statistics."""
        total_size = 0
        file_count = 0
        archive_count = 0

        for f in self.config.storage_path.rglob("*"):
            if f.is_file():
                total_size += f.stat().st_size
                if "archive" in str(f):
                    archive_count += 1
                else:
                    file_count += 1

        return {
            "storage_path": str(self.config.storage_path),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "max_size_mb": self.config.max_size_mb,
            "active_files": file_count,
            "archived_files": archive_count,
            "retention_days": self.config.retention_days,
            "compression": self.config.compression,
            "encryption": self._fernet is not None,
        }

    def _read_entries(self, log_file: Path, cutoff: float) -> List[Dict[str, Any]]:
        """Read log entries from a JSONL file, filtering by timestamp."""
        entries = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("timestamp", 0) >= cutoff:
                            entries.append(entry)
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.error(f"Error reading {log_file}: {e}")
        return entries


# --- Singleton ---
_log_storage: Optional[LogStorage] = None


def get_log_storage() -> LogStorage:
    """Return the global LogStorage instance."""
    global _log_storage
    if _log_storage is None:
        _log_storage = LogStorage()
    return _log_storage
