# Vigilant Operations & Deployment Guide

This guide provides instructions for deploying, administering, and maintaining **Vigilant Enterprise Network Defense** in production environments.

---

## 1. Deployment Strategies

Vigilant can be deployed in two modes depending on requirements for active mitigation controls.

### 1.1 Native Host Deployment (Full Control Mode - Recommended)
To allow Vigilant to block network ports via local firewalls and query process tables accurately, run it natively on the target operating system.

#### Windows Server
- **Service Integration:** Create a Windows Service for the Python backend using `NSSM` (Non-Sucking Service Manager) or task scheduler.
- **Privileges:** The backend executor account must belong to the local `Administrators` group to execute `netsh` rules.
- **Port Allocations:** Backend binds to `8600`, Frontend dev or production web server binds to standard HTTP/HTTPS ports.

#### Linux Enterprise (Ubuntu/RHEL)
- **Systemd Setup:** Create a service file in `/etc/systemd/system/vigilant.service`:
  ```ini
  [Unit]
  Description=Vigilant Enterprise Backend
  After=network.target

  [Service]
  Type=simple
  User=root
  WorkingDirectory=/opt/vigilant
  ExecStart=/opt/vigilant/.venv/bin/python3 -m backend.main
  Restart=always

  [Install]
  WantedBy=multi-user.target
  ```
- **Capabilities (Alternative to Root):** If running as non-root, you must grant raw socket permissions to the python executable:
  ```bash
  sudo setcap cap_net_raw,cap_net_admin+eip /opt/vigilant/.venv/bin/python3
  ```

---

### 1.2 Docker Containerized Deployment
While containerization limits direct firewall manipulations on the host, it is highly suitable for read-only networks or sensor nodes.

- **Capabilities Requirement:** The container must run with net-admin privileges. The `docker-compose.yml` must include:
  ```yaml
  cap_add:
    - NET_ADMIN
    - NET_RAW
  network_mode: "host"
  ```
- **Scaling:** Spawning multiple 센서 containers is possible as long as they listen on separate interfaces.

---

## 2. Database Administration

Vigilant uses SQLAlchemy which dynamically maps to SQLite or PostgreSQL engines.

### SQLite (WAL Mode)
- **File Location:** Configured via `DATABASE_URL` env variable. Default is `backend/data/sentinel.db`.
- **Automatic Backup:** Vigilant automatically duplicates and backs up the existing sqlite database file on startup under `backend/data/sentinel.db.bak` before verifying schemas.
- **Pruning:** By default, connection metrics older than 24 hours are pruned automatically every hour to maintain disk space.

### PostgreSQL (Production-Grade)
- For high-concurrency or multi-node clustering setups, configure PostgreSQL:
  ```env
  DATABASE_URL=postgresql://vigilant_user:secure_pwd@db-server:5432/vigilant
  ```
- Make sure to size the connection pool parameters (`pool_size`, `max_overflow`) appropriately in `backend/core/db.py`.

---

## 3. Log Storage & Retention

Application operations, automation actions, and security metrics are logged systematically.

### Archived Logs Encryption
If `LOG_ENCRYPTION_KEY` is configured in `.env`, rotated logs are automatically encrypted at rest using AES-256 (Fernet module from python `cryptography` library) before writing to disk.

### Gzip Compression
Rotated logs are packed into `.gz` archives to save up to 90% disk space.

### Retention Policy
The retention engine deletes archived files older than `LOG_RETENTION_DAYS` (default=90) during the hourly cleanup pass.

---

## 4. Troubleshooting Checklist

### 1. "Access denied reading net_connections" or Sniffer Startup Failures
- **Cause:** Lack of administrative privileges.
- **Solution:** Right-click Command Prompt/PowerShell and select **Run as Administrator** (Windows) or execute the launch script with `sudo` (Linux/macOS).

### 2. Sniffer Runs in "FALLBACK" mode
- **Cause:** Scapy was unable to bind to raw sockets, or WinPcap/NPcap driver is missing.
- **Solution (Windows):** Ensure `Npcap` or `WinPcap` is installed in "WinPcap API compatibility mode".
- **Solution (Linux):** Verify the user has the `CAP_NET_RAW` capability enabled.

### 3. Blank Web UI on Port 5173
- **Cause:** Javascript ESM import issues or React-Grid-Layout compilation failures.
- **Solution:** Run `npm run build` in the frontend directory and check compilation outputs. If running in developer mode, ensure that `react-grid-layout/legacy` subpath resolves properly in `DashboardPage.tsx`.

### 4. Logging Errors: `ValueError: I/O operation on closed file`
- **Cause:** Clean up hooks firing after the Python logging modules have already closed during exit.
- **Solution:** These alerts are benign shutdown messages. For completely silent exits, verify that the `atexit` routines do not call `logger` statements after system exit completes.
