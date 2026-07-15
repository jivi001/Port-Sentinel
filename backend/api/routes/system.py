"""
Vigilant API — System Information & Health Routes.

Endpoints:
  GET /api/info    — Detailed system information (auth required)
  GET /api/health  — Lightweight health check (public)
"""

import os
import time
import threading
import platform

import psutil
from fastapi import APIRouter



router = APIRouter(prefix="/api", tags=["System"])

PRODUCT_NAME = "Vigilant"
PRODUCT_FULL_NAME = "Vigilant Enterprise Network Defense"
VERSION = "2.0.0"

_start_time = time.time()


@router.get("/info")
async def system_info():
    """Detailed system information dashboard."""
    from backend.core.state import (
        get_sniffer_process, get_traffic_accumulator, get_policy_engine,
    )

    sniffer_process = get_sniffer_process()
    accumulator = get_traffic_accumulator()
    policy_engine = get_policy_engine()
    p = psutil.Process(os.getpid())

    return {
        "system": {
            "name": PRODUCT_FULL_NAME,
            "version": VERSION,
            "status": "Operational",
            "platform": platform.system(),
            "uptime_seconds": round(time.time() - _start_time, 2),
        },
        "resources": {
            "cpu_usage_percent": psutil.cpu_percent(),
            "memory_usage_mb": round(p.memory_info().rss / (1024 * 1024), 2),
            "threads_active": threading.active_count(),
        },
        "engine": {
            "sniffer_active": (
                sniffer_process.is_alive() if sniffer_process else False
            ),
            "ports_monitored": accumulator.cache.port_count(),
            "policies_loaded": len(policy_engine.policies),
        },
        "endpoints": {
            "api_health": "/api/health",
            "api_ports": "/api/ports",
            "api_blocked": "/api/blocked",
            "interactive_docs": "/docs",
        },
    }


@router.get("/health")
async def health():
    """Lightweight health check endpoint (unauthenticated)."""
    from backend.core.state import get_sniffer_process, get_traffic_accumulator

    sniffer = get_sniffer_process()
    accumulator = get_traffic_accumulator()

    return {
        "status": "ok",
        "product": PRODUCT_NAME,
        "version": VERSION,
        "platform": platform.system(),
        "sniffer_alive": sniffer.is_alive() if sniffer else False,
        "ports_tracked": accumulator.cache.port_count(),
        "uptime_seconds": round(time.time() - _start_time, 2),
    }
