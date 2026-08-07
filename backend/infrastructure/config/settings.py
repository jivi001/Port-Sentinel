"""
Infrastructure Configuration — Centralized application settings.

All configuration is loaded from environment variables with sensible
defaults. This replaces the scattered os.environ.get() calls in main.py.
"""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Settings:
    """Typed, immutable application configuration."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8600
    reload: bool = False

    # Database
    db_url: str = "sqlite:///vigilant_data.db"

    # Network capture
    emit_interval: float = 1.0
    db_flush_interval: float = 30.0
    cache_evict_interval: float = 3600.0

    # Shared memory IPC
    shm_name: str = "VigilantCapture"
    hmac_key: str = field(default_factory=lambda: secrets.token_hex(32))

    # CORS
    allowed_origins: List[str] = field(default_factory=lambda: [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5174",
    ])

    # Product metadata
    product_name: str = "Vigilant"
    product_full_name: str = "Vigilant Enterprise Network Defense"
    version: str = "2.0.0"

    # InfluxDB (optional)
    influx_url: str = ""
    influx_token: str = ""
    influx_org: str = ""
    influx_bucket: str = ""

    @property
    def influx_enabled(self) -> bool:
        return bool(self.influx_url and self.influx_token)


def load_settings() -> Settings:
    """Load settings from environment variables with defaults."""
    return Settings(
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8600")),
        reload=os.environ.get("RELOAD", "false").lower() == "true",
        db_url=os.environ.get("DATABASE_URL", "sqlite:///vigilant_data.db"),
        emit_interval=float(os.environ.get("EMIT_INTERVAL", "1.0")),
        db_flush_interval=float(os.environ.get("DB_FLUSH_INTERVAL", "30.0")),
        cache_evict_interval=float(os.environ.get("CACHE_EVICT_INTERVAL", "3600.0")),
        shm_name=os.environ.get("SENTINEL_SHM_NAME", "VigilantCapture"),
        hmac_key=os.environ.get("SENTINEL_HMAC_KEY", secrets.token_hex(32)),
        allowed_origins=[
            origin.strip()
            for origin in os.environ.get(
                "ALLOWED_ORIGINS",
                "http://localhost:3000,http://localhost:5173,http://localhost:5174",
            ).split(",")
        ],
        influx_url=os.environ.get("INFLUX_URL", ""),
        influx_token=os.environ.get("INFLUX_TOKEN", ""),
        influx_org=os.environ.get("INFLUX_ORG", ""),
        influx_bucket=os.environ.get("INFLUX_BUCKET", ""),
    )
