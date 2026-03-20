"""
Sentinel Backend Entry Point — main.py

FastAPI + Socket.io Dispatcher + Sniffer orchestration.

Architecture:
  1. FastAPI serves REST endpoints on :8600
  2. Socket.io pushes MsgPack-encoded port table at 1Hz to /ws
  3. Sniffer runs as a multiprocessing.Process with SharedMemory IPC
  4. Dispatcher thread reads SharedMemory → TrafficAccumulator → Socket.io emit
  5. atexit hook cleans up all Sentinel_ firewall rules

Startup requires elevated privileges:
  - Windows: Run as Administrator
  - macOS:   Run with sudo
"""

import sys
import os
import time
import signal
import atexit
import asyncio
import logging
import platform
import threading
from multiprocessing import shared_memory, Event as MPEvent
from contextlib import asynccontextmanager
from typing import Optional

import uvicorn
import msgpack
import psutil
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import socketio

# --- Project imports ---
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.sniffer import (
    SnifferProcess, read_all_active_ports,
    SHM_NAME, SHM_SIZE, ENTRY_SIZE,
)
from backend.core.metrics import TrafficAccumulator, PortSnapshot
from backend.core.db import SQLiteDB, InfluxDBWriter
from backend.core.exceptions import SystemProcessProtectionError, FirewallRuleError

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sentinel.main")

# --- Configuration ---
HOST = "0.0.0.0"
PORT = 8600
EMIT_INTERVAL = 1.0  # 1Hz Socket.io push
DB_FLUSH_INTERVAL = 60.0  # Flush traffic history to SQLite every 60s
EVICT_INTERVAL = 3600.0  # Evict stale cache every 1h

# --- OS Detection ---
PLATFORM = platform.system()
logger.info(f"Platform: {PLATFORM}")

# Import the appropriate OS adapter
if PLATFORM == "Windows":
    from backend.os_adapters import win32_bridge as os_bridge
elif PLATFORM == "Darwin":
    from backend.os_adapters import darwin_bridge as os_bridge
else:
    os_bridge = None
    logger.warning(f"Unsupported platform: {PLATFORM}. Control operations will be unavailable.")

# --- Global State ---
start_time = time.time()
sniffer_process: Optional[SnifferProcess] = None
sniffer_stop_event: Optional[MPEvent] = None
traffic_accumulator = TrafficAccumulator()
db = SQLiteDB()
influx = InfluxDBWriter()
dispatcher_running = False
shm: Optional[shared_memory.SharedMemory] = None


# --- Socket.io ---
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)


@sio.event
async def connect(sid, environ):
    logger.info(f"Client connected: {sid}")
    # Send initial port table on connect
    port_table = traffic_accumulator.get_port_table()
    packed = msgpack.packb(port_table, use_bin_type=True)
    await sio.emit("port_table", packed, room=sid)


@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")


# --- Psutil Fallback ---

def _psutil_fallback_entries() -> list:
    """
    Build port entries from psutil when the Scapy sniffer is unavailable.

    Returns a list of (port, bytes_in, bytes_out, pid, protocol, active) tuples
    using the same format that read_all_active_ports() returns from shared memory.

    NOTE: psutil cannot provide per-port byte counters (only system-wide via
    net_io_counters). So bytes_in/bytes_out are set to 0 and will produce 0 KB/s
    rates, but ports, PIDs, protocols, and app names are all accurate.
    """
    seen: dict[int, tuple] = {}
    try:
        for conn in psutil.net_connections(kind='inet'):
            if conn.status not in ('ESTABLISHED', 'LISTEN', 'CLOSE_WAIT', 'TIME_WAIT'):
                continue
            if not conn.laddr:
                continue
            port = conn.laddr.port
            pid = conn.pid or 0
            proto = 0 if conn.type == 1 else 1  # SOCK_STREAM=1=TCP, SOCK_DGRAM=2=UDP
            # Keep the first entry per port (usually the LISTEN or ESTABLISHED)
            if port not in seen:
                seen[port] = (port, 0, 0, pid, proto, 1)
    except (psutil.AccessDenied, PermissionError):
        logger.debug("Access denied reading net_connections for fallback")
    except Exception as e:
        logger.debug(f"Psutil fallback error: {e}")
    return list(seen.values())


# --- Dispatcher Loop (Async) ---

async def dispatcher_loop_async():
    """
    Async background task: reads SharedMemory → processes metrics → emits via Socket.io.

    Falls back to psutil when sniffer/shared-memory is unavailable.
    Runs at 1Hz (EMIT_INTERVAL).
    """
    global shm, dispatcher_running

    logger.info("Dispatcher task started")
    last_db_flush = time.time()
    last_evict = time.time()
    pending_db_records = []
    use_fallback = False

    # Try to attach to shared memory (sniffer may not have created it yet)
    shm_wait_start = time.time()
    while dispatcher_running:
        try:
            shm = shared_memory.SharedMemory(name=SHM_NAME, create=False, size=SHM_SIZE)
            logger.info("Dispatcher attached to shared memory")
            break
        except FileNotFoundError:
            # If sniffer hasn't created SHM after 10s, use psutil fallback
            if time.time() - shm_wait_start > 10:
                logger.warning("Shared memory not available after 10s — using psutil fallback")
                use_fallback = True
                break
            await asyncio.sleep(0.5)

    while dispatcher_running:
        try:
            now = time.time()

            # Read active ports from shared memory or psutil fallback
            if use_fallback:
                active_ports = _psutil_fallback_entries()
            else:
                try:
                    active_ports = read_all_active_ports(shm)
                except Exception as e:
                    logger.debug(f"SHM read error: {e}")
                    active_ports = []

                # If sniffer died and SHM is empty, switch to fallback
                if not active_ports:
                    fallback_entries = _psutil_fallback_entries()
                    if fallback_entries:
                        active_ports = fallback_entries

            # Process each port through the TrafficAccumulator
            for entry in active_ports:
                port, bytes_in, bytes_out, pid, protocol, active = entry
                snapshot = traffic_accumulator.process_port_data(
                    port=port,
                    bytes_in=bytes_in,
                    bytes_out=bytes_out,
                    pid=pid,
                    protocol=protocol,
                    timestamp=now,
                )

                # Queue for database flush
                pending_db_records.append({
                    "timestamp": snapshot.timestamp,
                    "port": snapshot.port,
                    "pid": snapshot.pid,
                    "app_name": snapshot.app_name,
                    "kb_s_in": snapshot.kb_s_in,
                    "kb_s_out": snapshot.kb_s_out,
                    "protocol": snapshot.protocol,
                    "direction": snapshot.direction,
                })

            # Get the full port table for emission
            port_table = traffic_accumulator.get_port_table()

            # MsgPack encode and emit via Socket.io
            packed = msgpack.packb(port_table, use_bin_type=True)
            await sio.emit("port_table", packed)

            # Periodic DB flush
            if now - last_db_flush >= DB_FLUSH_INTERVAL and pending_db_records:
                try:
                    db.insert_traffic(pending_db_records)
                    influx.write_traffic(pending_db_records)
                    pending_db_records.clear()
                    last_db_flush = now
                except Exception as e:
                    logger.warning(f"DB flush error: {e}")

            # Periodic cache eviction
            if now - last_evict >= EVICT_INTERVAL:
                traffic_accumulator.cleanup()
                db.prune_old_traffic(max_age_hours=24)
                last_evict = now

            await asyncio.sleep(EMIT_INTERVAL)

        except Exception as e:
            logger.error(f"Dispatcher error: {e}")
            await asyncio.sleep(EMIT_INTERVAL)

    logger.info("Dispatcher task stopped")


# --- Cleanup ---

def cleanup():
    """
    Cleanup hook — runs on exit (atexit + SIGTERM).

    Removes all Sentinel_ firewall rules and stops the sniffer.
    """
    global sniffer_process, dispatcher_running, shm

    logger.info("Cleanup starting...")
    dispatcher_running = False

    # Stop sniffer
    if sniffer_process and sniffer_process.is_alive():
        sniffer_process.stop()
        sniffer_process.join(timeout=5)
        logger.info("Sniffer process stopped")

    # Clean up shared memory
    if shm:
        try:
            shm.close()
        except Exception:
            pass

    # Clean up firewall rules
    if os_bridge:
        try:
            removed = os_bridge.cleanup_all_rules()
            logger.info(f"Cleaned up {removed} firewall rules")
        except Exception as e:
            logger.error(f"Firewall cleanup error: {e}")

    # Close databases
    db.close()
    influx.close()

    logger.info("Cleanup complete")


# Register cleanup
atexit.register(cleanup)

# Handle SIGTERM gracefully
def _sigterm_handler(signum, frame):
    logger.info("SIGTERM received")
    cleanup()
    sys.exit(0)

if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, _sigterm_handler)


# --- FastAPI Application ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown lifecycle."""
    global sniffer_process, sniffer_stop_event, dispatcher_running

    logger.info("Starting Sentinel backend...")

    # Initialize database
    db.connect()
    influx.connect()

    # Start sniffer process (non-fatal if it fails — psutil fallback will be used)
    try:
        sniffer_stop_event = MPEvent()
        sniffer_process = SnifferProcess(stop_event=sniffer_stop_event)
        sniffer_process.start()
        logger.info(f"Sniffer process launched (PID={sniffer_process.pid})")
    except Exception as e:
        logger.warning(f"Sniffer failed to start: {e} — using psutil fallback")
        sniffer_process = None

    # Start dispatcher task
    dispatcher_running = True
    asyncio.create_task(dispatcher_loop_async())

    yield

    # Shutdown
    cleanup()


app = FastAPI(
    title="Sentinel Unified Network Sentinel",
    version="1.2.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Socket.io
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


# --- REST Endpoints ---

@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "platform": PLATFORM,
        "sniffer_alive": sniffer_process.is_alive() if sniffer_process else False,
        "ports_tracked": traffic_accumulator.cache.port_count(),
        "uptime_seconds": round(time.time() - start_time, 2),
    }


@app.get("/api/ports")
async def get_ports():
    """Get current port table (REST fallback for Socket.io)."""
    return traffic_accumulator.get_port_table()


@app.get("/api/ports/{port}/history")
async def get_port_history(port: int, hours: int = 24):
    """Get traffic history for a specific port."""
    return db.get_traffic_history(port, hours=hours)


@app.post("/api/control/suspend/{pid}")
async def suspend_process_endpoint(pid: int):
    """Soft Block: Suspend a process."""
    if not os_bridge:
        raise HTTPException(status_code=501, detail="Unsupported platform")
    try:
        success = os_bridge.suspend_process(pid)
        if not success:
            if not psutil.pid_exists(pid):
                raise HTTPException(status_code=404, detail=f"Process PID {pid} not found")
            raise HTTPException(
                status_code=403,
                detail=f"Suspend denied for PID {pid}. Run backend with elevated privileges.",
            )
        return {"success": success, "pid": pid, "action": "suspend"}
    except SystemProcessProtectionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.post("/api/control/resume/{pid}")
async def resume_process_endpoint(pid: int):
    """Resume a previously suspended process."""
    if not os_bridge:
        raise HTTPException(status_code=501, detail="Unsupported platform")
    try:
        success = os_bridge.resume_process(pid)
        if not success:
            if not psutil.pid_exists(pid):
                raise HTTPException(status_code=404, detail=f"Process PID {pid} not found")
            raise HTTPException(
                status_code=403,
                detail=f"Resume denied for PID {pid}. Run backend with elevated privileges.",
            )
        return {"success": success, "pid": pid, "action": "resume"}
    except SystemProcessProtectionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.post("/api/control/kill/{pid}")
async def kill_process_endpoint(pid: int):
    """Kill a process."""
    if not os_bridge:
        raise HTTPException(status_code=501, detail="Unsupported platform")
    try:
        success = os_bridge.kill_process(pid)
        if not success:
            if not psutil.pid_exists(pid):
                raise HTTPException(status_code=404, detail=f"Process PID {pid} not found")
            raise HTTPException(
                status_code=403,
                detail=f"Kill denied for PID {pid}. Run backend with elevated privileges.",
            )
        return {"success": success, "pid": pid, "action": "kill"}
    except SystemProcessProtectionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.post("/api/control/block/{port}")
async def block_port_endpoint(port: int, protocol: str = "TCP"):
    """Hard Block: Add firewall rules to block a port."""
    if not os_bridge:
        raise HTTPException(status_code=501, detail="Unsupported platform")
    try:
        success = os_bridge.block_port(port, protocol)
        if success:
            db.add_blocked_port(port, block_type="hard", reason=f"User blocked {protocol}")
        return {"success": success, "port": port, "action": "block"}
    except FirewallRuleError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/control/unblock/{port}")
async def unblock_port_endpoint(port: int):
    """Remove firewall rules for a port."""
    if not os_bridge:
        raise HTTPException(status_code=501, detail="Unsupported platform")
    success = os_bridge.unblock_port(port)
    if success:
        db.remove_blocked_port(port)
    return {"success": success, "port": port, "action": "unblock"}


@app.get("/api/blocked")
async def get_blocked_ports():
    """Get list of currently blocked ports."""
    return db.get_blocked_ports()


# --- Entry Point ---

if __name__ == "__main__":
    logger.info(f"Starting Sentinel on {HOST}:{PORT}")
    uvicorn.run(
        socket_app,
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=False,
    )
