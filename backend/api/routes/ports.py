"""
Vigilant API — Port Monitoring Routes.

Endpoints:
  GET /api/ports               — Current live port table
  GET /api/ports/{port}/history — Historical traffic for a port
"""

from fastapi import APIRouter, Depends, Query
from fastapi import Path as FastAPIPath


from backend.core.db import get_database

router = APIRouter(prefix="/api/ports", tags=["Port Monitoring"])


@router.get("")
async def get_ports():
    """Current port table (REST fallback for Socket.IO)."""
    from backend.core.state import get_traffic_accumulator
    accumulator = get_traffic_accumulator()
    return accumulator.get_port_table()



