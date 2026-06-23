"""
Vigilant Database Migrations (migrations.py)

Handles startup migrations and automatic backups for SQLite database files.
"""

import os
import shutil
import logging
from pathlib import Path
from backend.core.models import Base

logger = logging.getLogger("vigilant.migrations")


def run_migrations(db) -> None:
    """
    Run database migrations and backup SQLite database if present.

    This function is idempotent and safe to run multiple times on startup.
    """
    if db._is_sqlite:
        # Resolve the SQLite database path from the connection string
        db_url = db.db_url or ""
        prefix = "sqlite:///"
        if db_url.startswith(prefix):
            db_path_str = db_url[len(prefix):]
            # Handle relative and absolute paths
            db_path = Path(db_path_str).resolve()
            if db_path.exists() and db_path.is_file():
                backup_path = db_path.with_name(f"{db_path.name}.bak")
                try:
                    # Perform copy backup before running migrations
                    shutil.copy2(db_path, backup_path)
                    logger.info(f"Automatic backup created: {backup_path}")
                except Exception as e:
                    logger.warning(f"Could not backup database: {e}")

    try:
        # Run SQLAlchemy metadata creation
        Base.metadata.create_all(bind=db.engine)
        logger.info("Database tables and indexes verified/created successfully.")
    except Exception as e:
        logger.critical(f"Database migration failed: {e}")
        raise
