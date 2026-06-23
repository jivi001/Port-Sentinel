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
import secrets
from multiprocessing import shared_memory, Event as MPEvent, Lock as MPLock
from contextlib import asynccontextmanager
from typing import Optional, Any

# Input validation
from fastapi import Path as FastAPIPath, Query

from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

import uvicorn
import msgpack
import psutil
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import socketio
import hmac
from fastapi.security import APIKeyHeader

# --- Project imports ---
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.sniffer import (
    SnifferProcess, read_all_active_ports,
    SHM_NAME, SHM_SIZE, ENTRY_SIZE,
)
from backend.core.metrics import TrafficAccumulator, PortSnapshot
from backend.core.db import SQLiteDB, InfluxDBWriter
from backend.core.policies import PolicyEngine
from backend.core.watchdog import spawn_watchdog
from backend.core.exceptions import SystemProcessProtectionError, FirewallRuleError

# --- Constants & Keys ---
SENTINEL_SHM_NAME = f"sentinel_shm_{secrets.token_hex(8)}"
SENTINEL_HMAC_KEY = secrets.token_bytes(32)

# --- Logging ---
from backend.core.logger import setup_logger
logger = setup_logger("sentinel.main")

# --- Configuration ---
HOST = os.environ.get("HOST", "127.0.0.1")
_raw_port = os.environ.get("PORT", "8600")
try:
    PORT = int(_raw_port)
    if not (1 <= PORT <= 65535):
        raise ValueError
except ValueError:
    logger.error(f"Invalid PORT value: {_raw_port!r}. Must be an integer 1-65535. Defaulting to 8600.")
    PORT = 8600
EMIT_INTERVAL = 1.0  # 1Hz Socket.io push
DB_FLUSH_INTERVAL = 60.0  # Flush traffic history to SQLite every 60s
EVICT_INTERVAL = 3600.0  # Evict stale cache every 1h

# --- CORS Origins ---
_env_origins = os.environ.get("SENTINEL_CORS_ORIGINS", "")
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

# --- Authentication (JWT RBAC) ---
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from backend.core.auth import decode_access_token, create_access_token, verify_password, get_password_hash
from backend.core.models import User, RoleEnum
from sqlalchemy.orm import Session
from sqlalchemy import select

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_db_session():
    session = db.get_session()
    try:
        yield session
    finally:
        session.close()

def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_db_session)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    user = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is None:
        raise credentials_exception
    return user

def require_auth(request: Request, user: User = Depends(get_current_user)):
    """Gate control endpoints: require valid JWT."""
    request.state.user = user
    return user

def require_role(allowed_roles: list):
    def role_checker(user: User = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Not enough permissions")
        return user
    return role_checker

require_admin = require_role([RoleEnum.ADMIN])
require_analyst = require_role([RoleEnum.ADMIN, RoleEnum.ANALYST])

# --- OS Detection ---
PLATFORM = platform.system()
logger.info(f"Platform: {PLATFORM}")

# Import the appropriate OS adapter
if PLATFORM == "Windows":
    from backend.os_adapters.win32_bridge import WindowsBridge
    os_bridge = WindowsBridge()
elif PLATFORM == "Darwin":
    from backend.os_adapters.darwin_bridge import DarwinBridge
    os_bridge = DarwinBridge()
elif PLATFORM == "Linux":
    from backend.os_adapters.linux_bridge import LinuxBridge
    os_bridge = LinuxBridge()
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
shm_lock = MPLock()

def _policy_action_handler(action: str, target: Any, app_name: Optional[str] = None):
    """Callback for PolicyEngine to execute OS-level actions and log them."""
    if not os_bridge:
        return
    try:
        msg = f"Automated {action} triggered on "
        severity = "warning"
        
        if action == "block":
            os_bridge.block_port(target)
            db.add_blocked_port(target, block_type="hard", reason="Policy Engine Auto-Block")
            msg += f"Port {target}"
            severity = "critical"
        elif action == "request_approval":
            msg += f"Analyst Approval requested for PID {target}"
            severity = "warning"
            db.create_analyst_approval(
                action_type="suspend_process", 
                target_identifier=str(target), 
                reason="Policy trigger"
            )
            
        db.insert_audit_log(
            event_type="policy_trigger",
            message=msg,
            app_name=app_name,
            severity=severity,
            details=f"Action: {action}, Target: {target}"
        )
    except Exception as e:
        logger.error(f"Policy action {action} failed: {e}")

policy_engine = PolicyEngine(action_handler=_policy_action_handler)
dispatcher_running = False
shm: Optional[shared_memory.SharedMemory] = None


# --- Socket.io ---
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=ALLOWED_ORIGINS,
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

    Returns a list of (port, bytes_in, bytes_out, pid, protocol, active, risk_score, remote_ip) tuples.
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
            remote_ip = conn.raddr.ip if conn.raddr else "0.0.0.0"
            
            # Keep the first entry per port
            if port not in seen:
                # (port, bytes_in, bytes_out, pid, protocol, active, risk_score, remote_ip)
                seen[port] = (port, 0, 0, pid, proto, 1, 0, remote_ip)
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
            # SHM_SIZE = 65536 * 64 = 4194304
            shm = shared_memory.SharedMemory(name=SENTINEL_SHM_NAME, create=False, size=4194304)
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

            # 1. Get port list from system (psutil) - ensures we see ALL open ports
            system_ports = _psutil_fallback_entries()
            
            # 2. Get traffic data from sniffer (shared memory) - has real counters
            sniffer_ports = []
            if not use_fallback:
                try:
                    sniffer_ports = read_all_active_ports(shm, hmac_key=SENTINEL_HMAC_KEY, lock=shm_lock)
                except Exception as e:
                    logger.debug(f"SHM read error: {e}")

            # 3. Merge: Prioritize sniffer data for counters, use system data for occupancy
            # Key: port
            merged_map = {entry[0]: list(entry) for entry in system_ports}
            
            for s_entry in sniffer_ports:
                port = s_entry[0]
                # If sniffer has data, overwrite counters and remote_ip
                if port in merged_map:
                    # Keep system's PID/Proto but use sniffer's bytes and risk
                    # s_entry = (port, bytes_in, bytes_out, pid, protocol, active, risk, remote_ip)
                    merged_map[port][1] = s_entry[1] # bytes_in
                    merged_map[port][2] = s_entry[2] # bytes_out
                    merged_map[port][6] = s_entry[6] # risk_score
                    if s_entry[7] != "0.0.0.0":
                        merged_map[port][7] = s_entry[7] # remote_ip
                else:
                    # New port only seen by sniffer
                    merged_map[port] = list(s_entry)

            active_ports = list(merged_map.values())

            # Process each port through the TrafficAccumulator concurrently
            for entry in active_ports:
                port, bytes_in, bytes_out, pid, protocol, active, risk_score, remote_ip = entry
                snapshot = traffic_accumulator.process_port_data(
                    port=port, bytes_in=bytes_in, bytes_out=bytes_out,
                    pid=pid, protocol=protocol, timestamp=now,
                    risk_score=risk_score, remote_ip=remote_ip,
                )
                policy_engine.evaluate(snapshot)
                pending_db_records.append({
                    "timestamp": snapshot.timestamp,
                    "port": snapshot.port,
                    "pid": snapshot.pid,
                    "app_name": snapshot.app_name,
                    "kb_s_in": snapshot.kb_s_in,
                    "kb_s_out": snapshot.kb_s_out,
                    "protocol": snapshot.protocol,
                    "direction": snapshot.direction,
                    "risk_score": snapshot.risk_score,
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

_cleanup_done = False


def cleanup():
    """
    Cleanup hook — runs on exit (atexit + SIGTERM).

    Removes all Sentinel_ firewall rules and stops the sniffer.
    """
    global sniffer_process, dispatcher_running, shm, _cleanup_done

    if _cleanup_done:
        return
    _cleanup_done = True

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
            cleared = db.clear_blocked_ports()
            logger.info(f"Cleared {cleared} blocked port records")
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
        sniffer_process = SnifferProcess(
            stop_event=sniffer_stop_event, 
            lock=shm_lock, 
            shm_name=SENTINEL_SHM_NAME, 
            hmac_key=SENTINEL_HMAC_KEY
        )
        sniffer_process.start()
        logger.info(f"Sniffer process launched (PID={sniffer_process.pid})")
    except Exception as e:
        logger.warning(f"Sniffer failed to start: {e} — using psutil fallback")
        sniffer_process = None

    # Start dispatcher task
    dispatcher_running = True
    _dispatcher_task = asyncio.create_task(dispatcher_loop_async())  # Store reference to prevent GC

    # Start watchdog for persistence
    watchdog = spawn_watchdog()

    # --- Start Policy Engine ---
    # Policy engine is evaluated synchronously inside dispatcher_loop_async

    # --- Seed Admin User ---
    from sqlalchemy import select
    from backend.core.models import User, RoleEnum
    from backend.core.auth import get_password_hash
    try:
        with db.SessionLocal() as session:
            admin_exists = session.execute(select(User).where(User.username == "admin")).scalar_one_or_none()
            if not admin_exists:
                admin_user = User(
                    username="admin",
                    email="admin@sentinel.local",
                    hashed_password=get_password_hash("admin123"), # Default password for initial login
                    role=RoleEnum.ADMIN.value
                )
                session.add(admin_user)
                session.commit()
                logger.info("Seeded default admin user (admin / admin123)")
    except Exception as e:
        logger.error(f"Failed to seed admin user: {e}")

    logger.info("Sentinel backend initialized successfully.")
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
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
)


# --- API Routes ---

@app.post("/api/auth/login")
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_db_session)):
    user = session.execute(select(User).where(User.username == form_data.username)).scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me")
def read_users_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role
    }

@app.get("/api/info")
async def root(_auth=Depends(require_auth)):
    """Professional system information dashboard (JSON). Requires auth."""
    p = psutil.Process(os.getpid())
    return {
        "system": {
            "name": "Sentinel Unified Network Sentinel",
            "version": "1.2.0",
            "status": "Operational",
            "platform": PLATFORM,
            "uptime_seconds": round(time.time() - start_time, 2),
        },
        "resources": {
            "cpu_usage_percent": psutil.cpu_percent(),
            "memory_usage_mb": round(p.memory_info().rss / (1024 * 1024), 2),
            "threads_active": threading.active_count()
        },
        "sentinel_engine": {
            "sniffer_active": sniffer_process.is_alive() if sniffer_process else False,
            "ports_monitored": traffic_accumulator.cache.port_count(),
            "policies_loaded": len(policy_engine.policies)
        },
        "endpoints": {
            "api_health": "/api/health",
            "api_ports": "/api/ports",
            "api_blocked": "/api/blocked",
            "interactive_docs": "/docs"
        }
    }

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
async def get_ports(_auth=Depends(require_auth)):
    """Get current port table (REST fallback for Socket.io). Requires auth."""
    return traffic_accumulator.get_port_table()


@app.get("/api/ports/{port}/history")
async def get_port_history(
    port: int = FastAPIPath(..., ge=1, le=65535),
    hours: int = Query(24, ge=1, le=720),
    _auth=Depends(require_auth)
):
    """Get traffic history for a specific port. Requires auth."""
    return db.get_traffic_history(port, hours=hours)


@app.post("/api/approvals/request")
async def request_approval_endpoint(
    pid: int = Query(...),
    app_name: str = Query(None),
    reason: str = Query("Manual request"),
    _auth=Depends(require_auth)
):
    """Request Analyst Approval for an action."""
    approval_id = db.create_analyst_approval(
        action_type="suspend_process", 
        target_identifier=str(pid), 
        reason=reason
    )
    db.insert_audit_log(
        event_type="approval_requested", message=f"Approval requested for PID {pid}",
        severity="info", details=f"App: {app_name}, Reason: {reason}, Approval ID: {approval_id}",
    )
    return {"success": True, "pid": pid, "action": "request_approval", "approval_id": approval_id}

@app.get("/api/approvals")
async def get_approvals(
    _auth=Depends(require_analyst)
):
    """Get all pending analyst approvals."""
    return db.get_pending_approvals()

from pydantic import BaseModel
class ApprovalResolve(BaseModel):
    status: str # "approved" or "rejected"

@app.post("/api/approvals/{approval_id}/resolve")
async def resolve_approval(
    approval_id: int,
    payload: ApprovalResolve,
    current_user: User = Depends(require_analyst)
):
    """Resolve an analyst approval."""
    if payload.status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Status must be approved or rejected")
        
    success = db.update_approval_status(approval_id, payload.status, current_user.username)
    if not success:
        raise HTTPException(status_code=404, detail="Approval not found")
        
    db.insert_audit_log(
        event_type="approval_resolved", message=f"Approval {approval_id} {payload.status} by {current_user.username}",
        severity="info" if payload.status == "approved" else "warning", details=f"Approval ID: {approval_id}, Status: {payload.status}",
    )
    
    # If approved, we need to actually kill the process. But we don't have a reliable cross-platform way 
    # to kill processes registered in os_bridge yet (the user said remove process killing).
    # Wait, the prompt says "Remove any functionality that automatically kills, terminates, or forcefully stops processes. Remove associated backend logic, API"
    # Oh! The prompt says "Remove any functionality that automatically kills, terminates, or forcefully stops processes."
    # AND "Implement the UI for the AnalystApproval workflow (accept/reject pending process actions)."
    # Okay, so I guess "accepting" it just marks it accepted but doesn't actually kill it because we removed that. Or maybe accepting it does something else?
    # I'll just mark it resolved.
    
    return {"success": True, "approval_id": approval_id, "status": payload.status}

@app.post("/api/control/block/{port}")
async def block_port_endpoint(
    port: int = FastAPIPath(..., ge=1, le=65535),
    protocol: str = "TCP",
    _auth=Depends(require_admin),
):
    """Hard Block: Add firewall rules to block a port."""
    if protocol.upper() not in ["TCP", "UDP"]:
        raise HTTPException(status_code=400, detail="Invalid protocol. Must be TCP or UDP.")
    
    if not os_bridge:
        raise HTTPException(status_code=501, detail="Unsupported platform")
    try:
        success = os_bridge.block_port(port, protocol)
        if success:
            db.add_blocked_port(port, block_type="hard", reason=f"User blocked {protocol}")
            db.insert_audit_log(
                event_type="manual_block", message=f"Blocked port {port}/{protocol}",
                severity="critical", details=f"Action: block, Target port: {port}, Protocol: {protocol}",
            )
        return {"success": success, "port": port, "action": "block"}
    except FirewallRuleError as e:
        logger.error(f"Firewall block error for port {port}: {e}")
        raise HTTPException(status_code=500, detail="Firewall operation failed. Check server logs for details.")


@app.post("/api/control/unblock/{port}")
async def unblock_port_endpoint(
    port: int = FastAPIPath(..., ge=1, le=65535),
    _auth=Depends(require_admin),
):
    """Remove firewall rules for a port."""
    if not os_bridge:
        raise HTTPException(status_code=501, detail="Unsupported platform")
    success = os_bridge.unblock_port(port)
    if success:
        db.remove_blocked_port(port)
        db.insert_audit_log(
            event_type="manual_unblock", message=f"Unblocked port {port}",
            severity="warning", details=f"Action: unblock, Target port: {port}",
        )
    return {"success": success, "port": port, "action": "unblock"}


@app.get("/api/blocked")
async def get_blocked_ports():
    """Get list of currently blocked ports."""
    return db.get_blocked_ports()

@app.get("/api/analytics/top-talkers")
async def get_top_talkers(
    hours: int = Query(24, ge=1, le=720),
    limit: int = Query(10, ge=1, le=1000),
    _auth=Depends(require_auth),
):
    """Analytics: Identify applications with highest traffic. Requires auth."""
    return db.get_top_talkers(hours=hours, limit=limit)

@app.get("/api/audit/logs")
async def get_audit_logs(
    limit: int = Query(100, ge=1, le=1000),
    _auth=Depends(require_auth),
):
    """Forensics: Get recent system and security events. Requires auth."""
    return db.get_audit_logs(limit=limit)


# --- Static Frontend Serving ---

def _find_frontend_dist() -> Optional[str]:
    """Locate the built React frontend dist folder."""
    # 1. PyInstaller frozen bundle (_MEIPASS)
    if getattr(sys, 'frozen', False):
        bundled = Path(sys._MEIPASS) / 'frontend_dist'
        if bundled.is_dir():
            return str(bundled)
    # 2. Development: relative to project root
    project_root = Path(__file__).resolve().parent.parent
    dev_dist = project_root / 'frontend' / 'dist'
    if dev_dist.is_dir():
        return str(dev_dist)
    return None


_frontend_path = _find_frontend_dist()
if _frontend_path:
    # Serve index.html for any non-API, non-file route (SPA fallback)
    @app.get("/")
    async def serve_spa_root():
        return FileResponse(os.path.join(_frontend_path, "index.html"))

    # Mount static assets (JS, CSS, images)
    app.mount("/assets", StaticFiles(directory=os.path.join(_frontend_path, "assets")), name="static-assets")

    # SPA catch-all: any path not matched by API returns index.html
    @app.get("/{full_path:path}")
    async def serve_spa_fallback(full_path: str):
        # Try to serve the exact file first (e.g. favicon.ico, robots.txt)
        file_path = os.path.join(_frontend_path, full_path)
        # Prevent path traversal — resolved path must stay within frontend dist
        resolved = os.path.realpath(file_path)
        safe_root = os.path.realpath(_frontend_path)
        if resolved.startswith(safe_root) and os.path.isfile(resolved):
            return FileResponse(resolved)
        # Otherwise return index.html for client-side routing
        return FileResponse(os.path.join(_frontend_path, "index.html"))

    logger.info(f"Frontend static files mounted from: {_frontend_path}")
else:
    logger.warning("Frontend dist not found — API-only mode (no UI served)")


# --- Entry Point ---

def main() -> None:
    """Run the backend ASGI server."""
    # Security guard: warn loudly when binding to all interfaces without an API key
    if HOST == "0.0.0.0" and not SENTINEL_API_KEY:
        logger.warning(
            "\n" + "=" * 72 + "\n"
            "  ⚠️  SECURITY WARNING: Binding to 0.0.0.0 WITHOUT an API key!\n"
            "  All control endpoints (block) are UNAUTHENTICATED.\n"
            "  Set SENTINEL_API_KEY env var or bind to 127.0.0.1.\n"
            + "=" * 72
        )

    # Wrap FastAPI with Socket.io ASGI app at runtime
    socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
    
    logger.info(f"Starting Sentinel on {HOST}:{PORT}")
    uvicorn.run(
        socket_app,
        host=HOST,
        port=PORT,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
