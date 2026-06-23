# Vigilant System Architecture

This document describes the high-level architecture, component communication patterns, and technical decisions behind **Vigilant Enterprise Network Defense**.

---

## 1. Architectural Blueprint

Vigilant is divided into two distinct zones:
1. **The Capture Plane (Data Plane):** A privileged sub-process running packet capturing.
2. **The Control Plane (Management Plane):** The core FastAPI REST / WebSocket servers, database models, and OS adapters.

```
+--------------------------------------------------------------+
|                        CAPTURE PLANE                         |
|                                                              |
|   [ Network Interface ]                                      |
|            |                                                 |
|            v (Raw Packets)                                   |
|   [ Scapy Packet Capture Sniffer ]                           |
|            |                                                 |
|            v (Write delta structures)                        |
|   [ 2MB Fixed-Size Shared Memory Map ]                       |
+--------------------------------------------------------------+
                             ||  (HMAC signed & verified)
                             ||  (Lock-free 1Hz read pass)
                             v
+--------------------------------------------------------------+
|                        CONTROL PLANE                         |
|                                                              |
|                  [ Async Dispatcher Loop ]                   |
|                        /           \                         |
|                       /             \                        |
|                      v               v                       |
|         [ Traffic Accumulator ]  [ Policy Engine ]           |
|                /       \                 |                   |
|               /         \                v                   |
|              v           v       [ Analyst Queue ]           |
|      [ SQLite/PostgreSQL ]       [ OS adapters ]             |
|              |                           |                   |
|              v                           v                   |
|     (MsgPack Broadcast)          (Firewall / netsh)          |
|      [ Socket.IO WS ]                                        |
+--------------------------------------------------------------+
```

---

## 2. Low-Level Capture & Shared Memory IPC

The core challenge of real-time Python-based packet analysis is avoiding the CPU overhead of Python's **Global Interpreter Lock (GIL)** and avoiding high serialization costs. 

### Multiprocessing Capture
Vigilant spawns a dedicated background process (`SnifferProcess`) that handles packet captures natively via `Scapy`. This process runs in its own execution thread on a separate CPU core.

### HMAC-Signed Shared Memory Map
Rather than using pipes, queues, or socket sockets, the capture process writes connection data directly to a **2MB fixed-size Shared Memory block (`multiprocessing.shared_memory.SharedMemory`)**.
- **Signing:** On every update, the capturing process writes the packet metrics array, computes an HMAC-SHA256 signature of the block using a randomized runtime key, and appends it to the end of the memory block.
- **Verification:** When the async dispatcher in the FastAPI thread reads the block, it first re-computes the HMAC. If it matches, the data is unpacked. If it doesn't match (indicating a partial write or write-collision), the read is immediately aborted and retried in the next event loop tick. This achieves **lock-free synchronization** between processes.

---

## 3. Platform Abstraction Layer (OS Adapters)

To operate seamlessly across Windows, macOS, and Linux, Vigilant abstracts all operating system interactions behind an object-oriented class structure (`BaseBridge`).

```
              +--------------------------+
              |   BaseBridge (Abstract)  |
              +--------------------------+
                /          |           \
               /           |            \
              v            v             v
      WindowsBridge   DarwinBridge   LinuxBridge
        (netsh)         (pfctl)      (nftables/iptables/ufw)
```

### Supported Platform Implementations
- **Windows (`win32_bridge`):** Uses ctypes and native Windows API functions to query TCP/UDP tables. Mutates firewall states using command calls against `netsh advfirewall`.
- **macOS (`darwin_bridge`):** Inspects connections using `lsof` and parses output. Configures firewalling by writing rules to `/etc/pf.conf` anchors and triggering `pfctl`.
- **Linux (`linux_bridge`):** Mapped via `/proc/net` files and `/proc` process mappings. Commands adapt to `nftables` or standard `iptables` and local `ufw` setups.

### Safety Guardrails
All adapters implement a strict blacklist of protected PIDs (e.g. system processes like PID `0` or `4` on Windows, or PID `1` on Linux/macOS). If a request targets one of these protected processes, the adapter throws a `SystemProcessProtectionError` and blocks the execution.

---

## 4. Analyst Approval Workflow

To prevent automated denial-of-service (such as a bad policy rule blocking critical internal system processes), the platform implements an **Analyst-in-the-Loop approval model**.

- No endpoints exist to terminate, kill, or suspend processes directly.
- The UI triggers `/api/approvals/request` which creates a ticket in the database.
- Security analysts review the pending ticket on the queue, inspect the telemetry, and click **Approve** or **Reject**.
- Only after manual approval does the backend execute the requested process suspension.

---

## 5. Frontend Visual Layout & 3D Globe

The user interface is designed for high-density, professional cybersecurity operations.

- **Design System:** Structured entirely with **Vanilla CSS** custom variables supporting unified dark/light themes. Colors are constrained to enterprise codes (White, Blue, Red, Neutral Gray) with no visual gradient clutter.
- **Widget Customization:** Built around `react-grid-layout`, allowing operators to drag, resize, and configure their dashboard modules (throughput area charts, recent audit logs, approvals, and metrics summaries). Layout coordinates are persisted to `localStorage` and synchronized with the backend.
- **3D Globe Visualization:** Replaces basic topological layouts with an interactive 3D WebGL globe (`react-globe.gl`). When threats are registered on active ports, they are geolocated and mapped as arcs connecting remote IPs to the local system node.
