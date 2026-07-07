"""
Vigilant API — Port Monitoring Routes.

Endpoints:
  GET /api/ports               — Current live port table
  GET /api/ports/{port}/history — Historical traffic for a port
"""

from fastapi import APIRouter, Depends, Query
from fastapi import Path as FastAPIPath
from backend.api.dependencies import get_current_user, get_traffic_accumulator

from backend.core.db import get_database

router = APIRouter(prefix="/api/ports", tags=["Port Monitoring"], dependencies=[Depends(get_current_user)])


@router.get("")
async def get_ports(accumulator = Depends(get_traffic_accumulator)):
    """Current port table (REST fallback for Socket.IO)."""
    return accumulator.get_port_table()



