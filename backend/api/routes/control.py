"""
Vigilant API — Firewall Control Routes.

Endpoints:
  POST /api/control/block/{port}   — Add firewall rule to block a port
  POST /api/control/unblock/{port} — Remove firewall rule for a port
  GET  /api/blocked                — List currently blocked ports
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as FastAPIPath

from backend.core.db import SQLiteDB, get_database
from backend.core.exceptions import FirewallRuleError
from backend.api.dependencies import get_current_user, get_os_bridge, get_influx, get_db_session

import asyncio

logger = logging.getLogger("vigilant.api.control")

router = APIRouter(tags=["Firewall Control"], dependencies=[Depends(get_current_user)])


@router.post("/api/control/block/{port}")
async def block_port_endpoint(
    port: int = FastAPIPath(..., ge=1, le=65535),
    protocol: str = Query("TCP"),
    os_bridge=Depends(get_os_bridge),
    influx=Depends(get_influx),
    db=Depends(get_db_session)
):
    """Add OS firewall rules to block inbound/outbound traffic on a port."""
    if protocol.upper() not in ("TCP", "UDP"):
        raise HTTPException(status_code=400, detail="Invalid protocol. Must be TCP or UDP.")

    if not os_bridge:
        raise HTTPException(status_code=501, detail="Unsupported platform")

    # The session yielded by get_db_session is an SQLAlchemy Session. 
    # Wait, the original code used `db = get_database()` to access `add_blocked_port` and `insert_audit_log` which are methods on `SQLiteDB`.
    # I should depend on `get_database` directly for those helper methods!
    from backend.core.db import get_database
    db_obj = get_database()

    try:
        success = await asyncio.to_thread(os_bridge.block_port, port, protocol)
        if success:
            await asyncio.to_thread(db_obj.add_blocked_port, port, block_type="hard", reason=f"User blocked {protocol}")
            await asyncio.to_thread(
                db_obj.insert_audit_log,
                event_type="manual_block",
                message=f"Blocked port {port}/{protocol}",
                severity="critical",
                details=f"Action: block, Target port: {port}, Protocol: {protocol}",
            )
            if influx:
                await asyncio.to_thread(influx.write_firewall_event, port, "block", protocol)
        return {"success": success, "port": port, "action": "block"}
    except FirewallRuleError as e:
        logger.error(f"Firewall block error for port {port}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Firewall operation failed. Check server logs.",
        )


@router.post("/api/control/unblock/{port}")
async def unblock_port_endpoint(
    port: int = FastAPIPath(..., ge=1, le=65535),
    os_bridge=Depends(get_os_bridge),
    influx=Depends(get_influx)
):
    """Remove Vigilant firewall rules for a specific port."""
    if not os_bridge:
        raise HTTPException(status_code=501, detail="Unsupported platform")

    from backend.core.db import get_database
    db_obj = get_database()
    
    success = await asyncio.to_thread(os_bridge.unblock_port, port)
    if success:
        await asyncio.to_thread(db_obj.remove_blocked_port, port)
        await asyncio.to_thread(
            db_obj.insert_audit_log,
            event_type="manual_unblock",
            message=f"Unblocked port {port}",
            severity="info",
            details=f"Action: unblock, Target port: {port}",
        )
        if influx:
            await asyncio.to_thread(influx.write_firewall_event, port, "unblock", "TCP")
    return {"success": success, "port": port, "action": "unblock"}


@router.get("/api/blocked")
async def get_blocked_ports():
    """List all currently blocked ports."""
    from backend.core.db import get_database
    db_obj = get_database()
    return await asyncio.to_thread(db_obj.get_blocked_ports)
