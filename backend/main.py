"""
Vigilant Backend Entry Point — main.py

Streamlined FastAPI application factory with:
  1. Router-based API organization
  2. Socket.IO real-time dispatch
  3. Scapy sniffer orchestration via multiprocessing
  4. Auto-initializing database with migration support
  5. Enterprise security middleware

Startup requires elevated privileges:
  - Windows: Run as Administrator
  - macOS/Linux: Run with sudo
"""

import sys
import os
import time
import signal
import atexit
import asyncio
import logging
import platform
import secrets
from multiprocessing import shared_memory, Event as MPEvent, Lock as MPLock
from contextlib import asynccontextmanager
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import uvicorn
import msgpack
import psutil
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import socketio

# --- Project imports ---
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.sniffer import SnifferProcess, read_all_active_ports, SHM_SIZE
from backend.core.metrics import TrafficAccumulator
from backend.core.db import SQLiteDB, InfluxDBWriter, get_database, set_database
from backend.core.policies import PolicyEngine
from backend.core.watchdog import spawn_watchdog
from backend.core.state import init_state, set_sniffer_process
from backend.core.logger import setup_logger
from backend.api.middleware import register_middleware

logger = setup_logger("vigilant.main")

# --- Product Metadata ---
PRODUCT_NAME = "Vigilant"
PRODUCT_FULL_NAME = "Vigilant Enterprise Network Defense"
VERSION = "2.0.0"

# --- Crypto Keys (per-instance) ---
SENTINEL_SHM_NAME = f"vigilant_shm_{secrets.token_hex(8)}"
SENTINEL_HMAC_KEY = secrets.token_bytes(32)

# --- Configuration ---
HOST = os.environ.get("HOST", "127.0.0.1")
_raw_port = os.environ.get("PORT", "8600")
try:
    PORT = int(_raw_port)
    if not (1 <= PORT <= 65535):
        raise ValueError
except ValueError:
    logger.error(f"Invalid PORT value: {_raw_port!r}. Defaulting to 8600.")
    PORT = 8600

EMIT_INTERVAL = 1.0
DB_FLUSH_INTERVAL = 60.0
EVICT_INTERVAL = 3600.0

# --- CORS Origins ---
_env_origins = (
    os.environ.get("VIGILANT_CORS_ORIGINS")
    or os.environ.get("SENTINEL_CORS_ORIGINS", "")
)
ALLOWED_ORIGINS = (
    [o.strip() for o in _env_origins.split(",") if o.strip()]
    if _env_origins
    else [
        "http://localhost:5173",
        "http://localhost:8600",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8600",
    ]
)

# --- OS Detection ---
PLATFORM = platform.system()
logger.info(f"Platform: {PLATFORM}")


def _create_os_bridge():
    """Load the platform-specific OS adapter."""
    if PLATFORM == "Windows":
        from backend.os_adapters.win32_bridge import WindowsBridge
        return WindowsBridge()
    elif PLATFORM == "Darwin":
        from backend.os_adapters.darwin_bridge import DarwinBridge
        return DarwinBridge()
    elif PLATFORM == "Linux":
        from backend.os_adapters.linux_bridge import LinuxBridge
        return LinuxBridge()
    logger.warning(f"Unsupported platform: {PLATFORM}. Control operations unavailable.")
    return None


os_bridge = _create_os_bridge()

# --- Global State ---
sniffer_process: Optional[SnifferProcess] = None
sniffer_stop_event: Optional[MPEvent] = None
traffic_accumulator = TrafficAccumulator()
db = SQLiteDB()
set_database(db)
influx = InfluxDBWriter()
shm_lock = MPLock()
dispatcher_running = False
shm: Optional[shared_memory.SharedMemory] = None


def _policy_action_handler(action, target, app_name=None):
    """Callback for PolicyEngine to execute OS-level actions and log them."""
    if not os_bridge:
        return
    try:
        msg = f"Automated {action} triggered on "
        severity = "warning"
        if action == "block":
            os_bridge.block_port(target)
            db.add_blocked_port(target, block_type="hard", reason="Policy Engine Auto-Block")
            if influx:
                influx.write_firewall_event(target, "auto-block", "TCP")
            msg += f"Port {target}"
            severity = "critical"
        elif action == "request_approval":
            msg += f"Analyst Approval requested for PID {target}"
            db.create_analyst_approval(
                action_type="suspend_process",
                target_identifier=str(target),
                reason="Policy trigger",
            )
        db.insert_audit_log(
            event_type="policy_trigger", message=msg,
            app_name=app_name, severity=severity,
            details=f"Action: {action}, Target: {target}",
        )
    except Exception as e:
        logger.error(f"Policy action {action} failed: {e}")


policy_engine = PolicyEngine(action_handler=_policy_action_handler)

# Initialize global state for route modules
init_state(
    db=db,
    traffic_accumulator=traffic_accumulator,
    policy_engine=policy_engine,
    os_bridge=os_bridge,
    influx=influx,
)

# --- Socket.IO ---
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=ALLOWED_ORIGINS,
    logger=False,
    engineio_logger=False,
)


@sio.event
async def connect(sid, environ):
    # Origin validation (CSRF protection)
    origin = environ.get("HTTP_ORIGIN")
    if origin and origin not in ALLOWED_ORIGINS:
        logger.warning(f"Socket.IO rejected: Invalid origin {origin}")
        return False

    logger.info(f"Client connected: {sid}")
    port_table = traffic_accumulator.get_port_table()
    packed = msgpack.packb(port_table, use_bin_type=True)
    await sio.emit("port_table", packed, room=sid)


@sio.event
async def disconnect(sid):
    logger.info(f"Client disconnected: {sid}")


# --- Psutil Fallback ---
def _psutil_fallback_entries() -> list:
    """Build port entries from psutil when Scapy sniffer is unavailable."""
    seen: dict[int, tuple] = {}
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.status not in ("ESTABLISHED", "LISTEN", "CLOSE_WAIT", "TIME_WAIT"):
                continue
            if not conn.laddr:
                continue
            port = conn.laddr.port
            pid = conn.pid or 0
            proto = 0 if conn.type == 1 else 1
            remote_ip = conn.raddr.ip if conn.raddr else "0.0.0.0"
            if port not in seen:
                seen[port] = (port, 0, 0, pid, proto, 1, 0, remote_ip)
    except (psutil.AccessDenied, PermissionError):
        logger.debug("Access denied reading net_connections for fallback")
    except Exception as e:
        logger.debug(f"Psutil fallback error: {e}")
    return list(seen.values())


# --- Dispatcher Loop ---
async def dispatcher_loop_async():
    """Async background task: reads SharedMemory → processes metrics → emits via Socket.IO."""
    global shm, dispatcher_running

    logger.info("Dispatcher task started")
    last_db_flush = time.time()
    last_evict = time.time()
    last_sys_metrics = time.time()
    pending_db_records = []
    use_fallback = False

    shm_wait_start = time.time()
    while dispatcher_running:
        try:
            shm = shared_memory.SharedMemory(
                name=SENTINEL_SHM_NAME, create=False, size=SHM_SIZE,
            )
            logger.info("Dispatcher attached to shared memory")
            break
        except FileNotFoundError:
            if time.time() - shm_wait_start > 10:
                logger.warning("Shared memory not available — using psutil fallback")
                use_fallback = True
                break
            await asyncio.sleep(0.5)

    while dispatcher_running:
        try:
            now = time.time()
            system_ports = _psutil_fallback_entries()
            sniffer_ports = []
            if not use_fallback:
                try:
                    # Optimized lock-free read: HMAC validation guarantees memory integrity
                    # without blocking the sniffer process's capture loop.
                    sniffer_ports = read_all_active_ports(
                        shm, hmac_key=SENTINEL_HMAC_KEY, lock=None,
                    )
                except Exception as e:
                    logger.debug(f"SHM read error: {e}")

            merged_map = {entry[0]: list(entry) for entry in system_ports}
            for s_entry in sniffer_ports:
                port = s_entry[0]
                if port in merged_map:
                    merged_map[port][1] = s_entry[1]
                    merged_map[port][2] = s_entry[2]
                    merged_map[port][6] = s_entry[6]
                    if s_entry[7] != "0.0.0.0":
                        merged_map[port][7] = s_entry[7]
                else:
                    merged_map[port] = list(s_entry)

            active_ports = list(merged_map.values())
            for entry in active_ports:
                port, bytes_in, bytes_out, pid, protocol, active, risk_score, remote_ip = entry
                snapshot = traffic_accumulator.process_port_data(
                    port=port, bytes_in=bytes_in, bytes_out=bytes_out,
                    pid=pid, protocol=protocol, timestamp=now,
                    risk_score=risk_score, remote_ip=remote_ip,
                )
                policy_engine.evaluate(snapshot)
                pending_db_records.append({
                    "timestamp": snapshot.timestamp, "port": snapshot.port,
                    "pid": snapshot.pid, "app_name": snapshot.app_name,
                    "kb_s_in": snapshot.kb_s_in, "kb_s_out": snapshot.kb_s_out,
                    "protocol": snapshot.protocol, "direction": snapshot.direction,
                    "risk_score": snapshot.risk_score,
                })

            port_table = traffic_accumulator.get_port_table()
            packed = msgpack.packb(port_table, use_bin_type=True)
            await sio.emit("port_table", packed)

            if now - last_db_flush >= DB_FLUSH_INTERVAL and pending_db_records:
                try:
                    influx.write_traffic(pending_db_records)
                    pending_db_records.clear()
                    last_db_flush = now
                except Exception as e:
                    logger.warning(f"DB flush error: {e}")

            if now - last_sys_metrics >= 5.0:
                try:
                    cpu = psutil.cpu_percent()
                    mem = psutil.virtual_memory().percent
                    procs = len(psutil.pids())
                    influx.write_system_metrics(cpu, mem, procs)
                    last_sys_metrics = now
                except Exception as e:
                    logger.debug(f"Sys metrics error: {e}")

            if now - last_evict >= EVICT_INTERVAL:
                traffic_accumulator.cleanup()
                last_evict = now

            await asyncio.sleep(EMIT_INTERVAL)
        except Exception as e:
            logger.error(f"Dispatcher error: {e}")
            await asyncio.sleep(EMIT_INTERVAL)

    logger.info("Dispatcher task stopped")


# --- Cleanup ---
_cleanup_done = False


def cleanup():
    """Cleanup hook — runs on exit. Removes firewall rules and stops sniffer."""
    global sniffer_process, dispatcher_running, shm, _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True

    logger.info("Cleanup starting...")
    dispatcher_running = False

    if sniffer_process and sniffer_process.is_alive():
        sniffer_process.stop()
        sniffer_process.join(timeout=5)
        logger.info("Sniffer process stopped")

    if shm:
        try:
            shm.close()
        except Exception:
            pass

    if os_bridge:
        try:
            removed = os_bridge.cleanup_all_rules()
            logger.info(f"Cleaned up {removed} firewall rules")
            cleared = db.clear_blocked_ports()
            logger.info(f"Cleared {cleared} blocked port records")
        except Exception as e:
            logger.error(f"Firewall cleanup error: {e}")

    db.close()
    influx.close()
    logger.info("Cleanup complete")


atexit.register(cleanup)

if hasattr(signal, "SIGTERM"):
    def _sigterm_handler(signum, frame):
        logger.info("SIGTERM received")
        cleanup()
        sys.exit(0)
    signal.signal(signal.SIGTERM, _sigterm_handler)



# --- FastAPI Application ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown lifecycle."""
    global sniffer_process, sniffer_stop_event, dispatcher_running

    logger.info(f"Starting {PRODUCT_FULL_NAME} v{VERSION}...")

    # Initialize database (auto-creates tables)
    db.connect()
    influx.connect()

    # Start sniffer process
    try:
        sniffer_stop_event = MPEvent()
        sniffer_process = SnifferProcess(
            stop_event=sniffer_stop_event, lock=shm_lock,
            shm_name=SENTINEL_SHM_NAME, hmac_key=SENTINEL_HMAC_KEY,
        )
        sniffer_process.start()
        set_sniffer_process(sniffer_process)
        logger.info(f"Sniffer process launched (PID={sniffer_process.pid})")
    except Exception as e:
        logger.warning(f"Sniffer failed to start: {e} — using psutil fallback")
        sniffer_process = None

    # Start dispatcher
    dispatcher_running = True
    asyncio.create_task(dispatcher_loop_async())

    # Start watchdog
    spawn_watchdog()



    logger.info(f"{PRODUCT_FULL_NAME} initialized successfully.")
    yield
    cleanup()


app = FastAPI(
    title=PRODUCT_FULL_NAME,
    version=VERSION,
    lifespan=lifespan,
)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)
register_middleware(app)

from backend.api.routes.ports import router as ports_router
from backend.api.routes.control import router as control_router
from backend.api.routes.approvals import router as approvals_router

from backend.api.routes.system import router as system_router

app.include_router(ports_router)
app.include_router(control_router)
app.include_router(approvals_router)

app.include_router(system_router)

# --- Static Frontend Serving ---
def _find_frontend_dist() -> Optional[str]:
    """Locate the built React frontend dist folder."""
    if getattr(sys, "frozen", False):
        bundled = Path(sys._MEIPASS) / "frontend_dist"
        if bundled.is_dir():
            return str(bundled)
    project_root = Path(__file__).resolve().parent.parent
    dev_dist = project_root / "frontend" / "dist"
    if dev_dist.is_dir():
        return str(dev_dist)
    return None


_frontend_path = _find_frontend_dist()
if _frontend_path:
    @app.get("/")
    async def serve_spa_root():
        return FileResponse(os.path.join(_frontend_path, "index.html"))

    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(_frontend_path, "assets")),
        name="static-assets",
    )

    @app.get("/{full_path:path}")
    async def serve_spa_fallback(full_path: str):
        file_path = os.path.join(_frontend_path, full_path)
        resolved = os.path.realpath(file_path)
        safe_root = os.path.realpath(_frontend_path)
        if resolved.startswith(safe_root) and os.path.isfile(resolved):
            return FileResponse(resolved)
        return FileResponse(os.path.join(_frontend_path, "index.html"))

    logger.info(f"Frontend static files mounted from: {_frontend_path}")
else:
    logger.warning("Frontend dist not found — API-only mode")


socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


# --- Entry Point ---
def main() -> None:
    """Run the Vigilant ASGI server."""
    logger.info(f"Starting {PRODUCT_NAME} on {HOST}:{PORT}")
    uvicorn.run(socket_app, host=HOST, port=PORT, log_level="info", access_log=False)


if __name__ == "__main__":
    main()
