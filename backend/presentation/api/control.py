"""
Presentation API — Control routes (firewall block/unblock).

Thin controllers that dispatch to CQRS command handlers.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.application.commands.firewall import (
    BlockPortCommand,
    FirewallCommandHandler,
    UnblockPortCommand,
)
from backend.presentation.dependencies.injection import get_firewall_handler

router = APIRouter(prefix="/api/control", tags=["control"])


@router.post("/block/{port}")
async def block_port(
    port: int,
    protocol: str = "TCP",
    handler: FirewallCommandHandler = Depends(get_firewall_handler),
) -> dict:
    """Block a port via OS firewall."""
    if not (1 <= port <= 65535):
        raise HTTPException(status_code=400, detail="Port must be 1–65535")

    protocol = protocol.upper()
    if protocol not in ("TCP", "UDP"):
        raise HTTPException(status_code=400, detail="Protocol must be TCP or UDP")

    try:
        return handler.handle_block(
            BlockPortCommand(port=port, protocol=protocol)
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/unblock/{port}")
async def unblock_port(
    port: int,
    handler: FirewallCommandHandler = Depends(get_firewall_handler),
) -> dict:
    """Remove a firewall rule for a port."""
    if not (1 <= port <= 65535):
        raise HTTPException(status_code=400, detail="Port must be 1–65535")

    return handler.handle_unblock(UnblockPortCommand(port=port))
