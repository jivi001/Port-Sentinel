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

from backend.api.dependencies import require_admin, require_auth
from backend.core.db import get_database
from backend.core.exceptions import FirewallRuleError

logger = logging.getLogger("vigilant.api.control")

router = APIRouter(tags=["Firewall Control"])


@router.post("/api/control/block/{port}")
async def block_port_endpoint(
    port: int = FastAPIPath(..., ge=1, le=65535),
    protocol: str = Query("TCP"),
    _auth=Depends(require_admin),
):
    """Add OS firewall rules to block inbound/outbound traffic on a port."""
    if protocol.upper() not in ("TCP", "UDP"):
        raise HTTPException(status_code=400, detail="Invalid protocol. Must be TCP or UDP.")

    from backend.core.state import get_os_bridge
    os_bridge = get_os_bridge()
    if not os_bridge:
        raise HTTPException(status_code=501, detail="Unsupported platform")

    db = get_database()
    try:
        success = os_bridge.block_port(port, protocol)
        if success:
            db.add_blocked_port(port, block_type="hard", reason=f"User blocked {protocol}")
            db.insert_audit_log(
                event_type="manual_block",
                message=f"Blocked port {port}/{protocol}",
                severity="critical",
                details=f"Action: block, Target port: {port}, Protocol: {protocol}",
            )
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
    _auth=Depends(require_admin),
):
    """Remove Vigilant firewall rules for a specific port."""
    from backend.core.state import get_os_bridge
    os_bridge = get_os_bridge()
    if not os_bridge:
        raise HTTPException(status_code=501, detail="Unsupported platform")

    db = get_database()
    success = os_bridge.unblock_port(port)
    if success:
        db.remove_blocked_port(port)
        db.insert_audit_log(
            event_type="manual_unblock",
            message=f"Unblocked port {port}",
            severity="warning",
            details=f"Action: unblock, Target port: {port}",
        )
    return {"success": success, "port": port, "action": "unblock"}


@router.get("/api/blocked")
async def get_blocked_ports(_auth=Depends(require_auth)):
    """List all currently blocked ports."""
    db = get_database()
    return db.get_blocked_ports()
