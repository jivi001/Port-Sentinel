"""
Presentation WebSocket — Socket.IO handlers.
"""

from __future__ import annotations

import logging
import socketio
from typing import List
from msgpack import packb

logger = logging.getLogger("vigilant.websocket")

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)


@sio.event
async def connect(sid: str, environ: dict) -> None:
    """Handle new client connection."""
    logger.debug("Socket.IO client connected: %s", sid)


@sio.event
async def disconnect(sid: str) -> None:
    """Handle client disconnection."""
    logger.debug("Socket.IO client disconnected: %s", sid)


async def emit_port_table(port_table: List[dict]) -> None:
    """Emit the current port table to all connected clients via MsgPack."""
    try:
        if port_table:
            packed_data = packb(port_table)
            await sio.emit("port_table", packed_data)
    except Exception:
        logger.exception("Failed to emit port table")
