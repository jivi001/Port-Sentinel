# Port Sentinel

Port Sentinel is a real-time network visibility and response console.  
It monitors live port/process activity, enriches traffic with threat intelligence, and provides operator controls like process suspend/kill and firewall block/unblock.

This README is a detailed technical guide for:
- What each part of the project does
- Technologies and packages used
- Core runtime logic and data flow
- Setup, configuration, API surface, and troubleshooting

## 1. What Is What (Project Layout)

```text
Port Sentinel/
├─ backend/                  # FastAPI + Socket.IO backend and OS control layer
│  ├─ main.py                # App entrypoint, orchestration, API endpoints
│  ├─ core/
│  │  ├─ sniffer.py          # Scapy packet capture process + shared memory writer
│  │  ├─ metrics.py          # Byte delta -> KB/s logic + live cache
│  │  ├─ db.py               # SQLite + InfluxDB + Supabase helper classes
│  │  ├─ policies.py         # Automation policy engine
│  │  ├─ threat_intel.py     # IP enrichment + risk scoring
│  │  ├─ watchdog.py         # Side monitor to restart backend if terminated
│  │  └─ exceptions.py       # Domain exceptions (safety and control errors)
│  ├─ os_adapters/
│  │  ├─ win32_bridge.py     # Windows process + firewall controls
│  │  ├─ darwin_bridge.py    # macOS process + pfctl controls
│  │  └─ android_bridge.kt   # Android-related bridge code (not main desktop path)
│  └─ data/                  # Local SQLite DB files
├─ frontend/                 # React + TypeScript dashboard
│  ├─ src/pages/             # Main views (dashboard, processes, settings, etc.)
│  ├─ src/components/        # Reusable UI components
│  ├─ src/hooks/             # Socket context/hooks
│  ├─ src/services/          # API client and transport fallback logic
│  └─ nginx.conf             # Production reverse-proxy config for container frontend
├─ tests/                    # Unit, integration, safety, and stress tests
├─ docker-compose.yml        # Multi-service deployment (frontend + backend)
├─ run.bat                   # Windows dev startup script
└─ run.sh                    # Unix/macOS dev startup script
```

## 2. System Architecture (How It Works)

At runtime, Port Sentinel is split into two major planes:

1. Data Plane (traffic capture + metrics)
- `SnifferProcess` captures packets via Scapy.
- It writes compact per-port counters into shared memory.
- Dispatcher loop reads shared memory + psutil connection snapshots.
- `TrafficAccumulator` computes KB/s and emits live table snapshots.

2. Control Plane (operator actions + policy actions)
- REST endpoints in FastAPI execute control actions.
- OS adapters perform process and firewall operations.
- Policy engine can auto-trigger actions based on traffic/risk thresholds.
- Audit and block state persist to SQLite.

High-level flow:

```text
Network Packets
   -> Scapy Sniffer Process
   -> Shared Memory (2MB fixed map)
   -> Dispatcher (1Hz loop)
   -> Metrics + Threat Enrichment + Policy Evaluation
   -> Socket.IO MsgPack stream + REST endpoints
   -> React Dashboard
```

## 3. Core Runtime Logic

### 3.1 Capture + Shared Memory
- `backend/core/sniffer.py` runs as a separate process.
- Packet callback accumulates bytes by source/destination port.
- Data is flushed to shared memory at short intervals (`CAPTURE_INTERVAL`).
- Shared memory layout stores:
  - port
  - inbound/outbound byte counters
  - PID
  - protocol
  - active flag
  - risk score
  - remote IP

Why shared memory: low-overhead IPC with predictable fixed-size structure.

### 3.2 Dispatcher + Merge Strategy
- `backend/main.py` async dispatcher runs every second.
- It gathers:
  - psutil connection state (occupancy/source-of-truth for open ports)
  - sniffer counters (actual traffic deltas/risk)
- Merge logic prioritizes sniffer counters but retains system-level visibility.
- Output is emitted over Socket.IO as MsgPack and exposed via `/api/ports`.

### 3.3 Metrics and Cache
- `backend/core/metrics.py` computes byte deltas to KB/s.
- A cache stores snapshots per port.
- Live table returns only recently active ports (TTL window), avoiding stale dead entries in UI.

### 3.4 Threat Intelligence
- `backend/core/threat_intel.py` enriches remote IP metadata using ipinfo.io.
- Metadata includes `org`, `country`, and a simple risk score.
- Results are cached in-memory to avoid repeated remote lookups.

### 3.5 Policy Engine
- `backend/core/policies.py` evaluates snapshots against enabled policy conditions:
  - minimum traffic threshold
  - minimum risk threshold
  - app filters/include-exclude
- On match, it calls action handler for `kill`, `block`, or `suspend`.
- Trigger cooldown prevents rapid repeated actions.

### 3.6 OS Control Adapters
- Windows (`win32_bridge.py`):
  - process ops via `psutil`
  - firewall ops via `netsh advfirewall`
  - protected PIDs guarded (`0`, `4`)
- macOS (`darwin_bridge.py`):
  - process ops via `psutil`
  - firewall ops via `pfctl`
  - protected PIDs guarded (`0`, `1`)

### 3.7 Cleanup + Watchdog
- On shutdown (`atexit` + `SIGTERM`), backend:
  - stops sniffer
  - cleans firewall rules (`Sentinel_` namespace)
  - clears blocked-port records accordingly
  - closes DB writers
- Watchdog can respawn backend if main PID disappears.

## 4. Technologies Used

### Backend
- Python 3.10+
- FastAPI + Uvicorn (`REST API`)
- python-socketio (`real-time push`)
- Scapy (`packet sniffing`)
- psutil (`process/connection/process-control helpers`)
- msgpack (`compact wire payload for high-frequency updates`)
- SQLite (`local persistence`)
- InfluxDB client (optional time-series output)
- Supabase client (optional cloud sync/auth hooks)

### Frontend
- React 18 + TypeScript
- Vite (dev/build tooling)
- socket.io-client (live stream)
- @msgpack/msgpack (decode live payloads)
- @tanstack/react-virtual (efficient large-list rendering)
- recharts (visual analytics)
- react-router-dom (routing)

### DevOps / Runtime
- Docker + Docker Compose
- Nginx (frontend static serving + API reverse proxy in container mode)

## 5. Package-by-Package Reference

### Python dependencies (`pyproject.toml`)
- `fastapi`, `uvicorn[standard]`: API server and ASGI hosting
- `python-socketio`, `python-engineio`: bidirectional real-time channel
- `scapy`: packet capture and parsing
- `psutil`: process/network system introspection + process controls
- `msgpack`: low-overhead serialization for live socket payloads
- `aiosqlite`: async-friendly SQLite access support
- `influxdb-client`: optional time-series persistence
- `supabase`: optional remote auth/data sync
- `requests`: external HTTP lookups (e.g., IP metadata)

### Frontend dependencies (`frontend/package.json`)
- `react`, `react-dom`: UI runtime
- `react-router-dom`: route shell and navigation
- `socket.io-client`: stream transport
- `@msgpack/msgpack`: decode backend-packed table data
- `@tanstack/react-virtual`: high-performance table virtualization
- `recharts`: chart rendering for trends

## 6. API Endpoints

Base backend URL: `http://localhost:8600`

### Health and Data
- `GET /api/health`  
  Backend liveness, platform, uptime, tracked ports.
- `GET /api/ports`  
  Current live port table (REST fallback).
- `GET /api/ports/{port}/history?hours=24`  
  Historical snapshots for a specific port.
- `GET /api/blocked`  
  Current blocked-port records.
- `GET /api/analytics/top-talkers?hours=24&limit=10`  
  Top traffic-generating apps.
- `GET /api/audit/logs?limit=100`  
  Recent audit/security events.

### Control
- `POST /api/control/suspend/{pid}`
- `POST /api/control/resume/{pid}`
- `POST /api/control/kill/{pid}`
- `POST /api/control/block/{port}?protocol=TCP|UDP`
- `POST /api/control/unblock/{port}`

Response pattern:
```json
{
  "success": true,
  "pid": 1234,
  "port": 443,
  "action": "kill|block|..."
}
```

## 7. Data Model and Persistence

Primary local DB: `backend/data/sentinel.db`

Key tables:
- `traffic_history`: time-series traffic snapshots
- `blocked_ports`: current block state for operator UI/control
- `process_map`: PID-to-name cache support
- `config_cache`: app config key-value cache
- `audit_logs`: policy and control action history

Optional integrations:
- InfluxDB (time-series sink)
- Supabase (auth/sync extensions)

## 8. Setup and Run

### 8.1 Native (recommended for full control features)

Windows:
1. Open terminal as **Administrator**
2. Run:
   ```bat
   run.bat
   ```

macOS/Linux:
1. Use elevated shell when needed for sniff/firewall operations
2. Run:
   ```bash
   ./run.sh
   ```

Frontend dev URL: `http://localhost:5173`  
Backend API URL: `http://localhost:8600`

### 8.2 Docker

```bash
docker compose up --build
```

Frontend URL (containerized): `http://localhost:8080`  
Backend URL (mapped): `http://localhost:8600`

Note: process/firewall controls depend on host OS capabilities and privileges.  
Containerized Linux backend will not provide Windows/macOS-native control adapters.

## 9. Configuration

Environment variables used:
- `HOST` (default `0.0.0.0`)
- `PORT` (default `8600`)
- `IPINFO_TOKEN` (for IP enrichment in threat intel module)
- `INFLUXDB_URL`, `INFLUXDB_TOKEN`, `INFLUXDB_ORG`, `INFLUXDB_BUCKET` (optional)
- `SUPABASE_URL`, `SUPABASE_KEY` (optional)

Create `.env` in project root to override defaults.

## 10. Frontend Logic Notes

- Frontend uses a shared socket context to avoid duplicate websocket connections.
- API service uses proxy-first strategy (`/api`) with direct-backend fallback for dev resilience.
- Process and settings pages use confirmation modals for destructive actions.
- Success/failure messages are shown in-page for operator feedback.

## 11. Testing Strategy

Test tiers under `tests/`:
- `unit/`: isolated logic (metrics, endpoint semantics, callbacks)
- `integration/`: command generation + socket dispatch behavior
- `safety/`: protected PID guards + cleanup behavior
- `stress/`: high-load behavior

Run all:
```bash
pytest -q
```

Run selected:
```bash
pytest tests/unit/test_metrics.py -q
pytest tests/integration/test_firewall_commands.py -q
pytest tests/unit/test_control_endpoints.py -q
```

## 12. Security and Safety Guardrails

- System-critical PIDs are protected from kill/suspend/resume.
- Block/unblock operations are scoped to Sentinel-managed rule naming.
- Cleanup removes Sentinel firewall rules on shutdown.
- Control endpoints return explicit HTTP errors for:
  - unsupported platform
  - missing process
  - permission denied

## 13. Common Troubleshooting

### `TERMINATE` / `RESTORE` not working
- Ensure backend is running with elevated privileges:
  - Windows: Administrator terminal
  - macOS: run with `sudo` where required
- Check platform support:
  - Control adapters are implemented for Windows and macOS in this repo.
- Validate backend health:
  - `GET /api/health`
- Check browser/API error payload for exact denial reason (`403/404/501`).

### No live traffic shown
- Confirm sniffer dependencies and capture privileges are available.
- Backend can fallback to psutil occupancy view if shared memory/sniffer is unavailable.

### Build issue: `tsc is not recognized`
- Install frontend dependencies:
  ```bash
  cd frontend
  npm ci
  ```

## 14. License

MIT
