"""
Vigilant API — Port Monitoring Routes.

Endpoints:
  GET /api/ports               — Current live port table
  GET /api/ports/{port}/history — Historical traffic for a port
"""

from fastapi import APIRouter, Depends, Query
from fastapi import Path as FastAPIPath

from backend.api.dependencies import require_auth
from backend.core.db import get_database

router = APIRouter(prefix="/api/ports", tags=["Port Monitoring"])


@router.get("")
async def get_ports(_auth=Depends(require_auth)):
    """Current port table (REST fallback for Socket.IO)."""
    from backend.core.state import get_traffic_accumulator
    accumulator = get_traffic_accumulator()
    return accumulator.get_port_table()


@router.get("/{port}/history")
async def get_port_history(
    port: int = FastAPIPath(..., ge=1, le=65535),
    hours: int = Query(24, ge=1, le=720),
    _auth=Depends(require_auth),
):
    """Historical traffic snapshots for a specific port."""
    db = get_database()
    return db.get_traffic_history(port, hours=hours)
