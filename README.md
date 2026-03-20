# Sentinel Unified Network Sentinel

### Executive Summary
Sentinel is a high-performance network monitoring and administrative control system designed for real-time visibility into system-wide port traffic and process-level network attribution. The system leverages low-level packet sniffing and OS-specific kernel bridges to provide precise traffic metrics, historical logging, and active mitigation capabilities such as port-level firewall blocking and process suspension. It is architected for low-latency data propagation using shared memory IPC and MsgPack-encoded WebSocket streams, supporting Windows, macOS, and Android platforms.

### Core Functionality
* **Real-time Network Monitoring**: Captures and attributes inbound/outbound traffic to specific local ports and processes using Scapy-based sniffing.
* **Multi-Platform Process Attribution**: Maps active network connections to specific System PIDs and application names using persistent discovery logic across Windows, macOS, and Android.
* **High-Resolution Metrics**: Calculates instantaneous transfer rates (KB/s) and maintains a 24-hour sliding window of traffic history.
* **Administrative Control**: Provides RESTful endpoints for suspending, resuming, or terminating processes associated with network activity.
* **Dynamic Firewall Integration**: Enables "Hard Block" operations by injecting OS-level firewall rules (Windows Filtering Platform, macOS PF) to drop traffic on specified ports.
* **Android VPN Sentinel**: Includes a specialized Kotlin bridge utilizing the VpnService API for packet interception and UID-based app attribution on mobile devices.
* **Persistent & Time-Series Logging**: Synchronizes real-time metrics to a SQLite backend for local auditing and InfluxDB for high-scale time-series analysis.
* **Cloud Synchronization**: Integrated Supabase support for user authentication and cross-device synchronization of blocked port policies.

### Technical Stack
* **Backend**: Python 3.12, FastAPI (REST API), Socket.io (Real-time events), Scapy (L2/L3 Packet Sniffing).
* **Mobile Bridge**: Kotlin (Android VpnService), JNI (Native Shared Memory Bridge).
* **Frontend**: React 18, TypeScript, Vite, Socket.io-client, CSS Modules.
* **Storage**: 
    * SQLite (Local state & history)
    * InfluxDB 2.x (Time-series telemetry)
    * Supabase (Cloud policy sync & Auth)
* **Serialization**: MsgPack (Binary serialization for low-latency telemetry).
* **IPC**: Python Multiprocessing SharedMemory (Zero-copy counter exchange between sniffer and dispatcher).

### Architecture & Logic
The system operates through a decoupled, multi-process architecture optimized for minimal performance overhead:
1. **Sniffer Process**: A dedicated high-priority process utilizing Scapy to capture packets at 10Hz. It writes raw byte counters directly into a 2MB fixed-allocation SharedMemory segment, bypassing the Python Global Interpreter Lock (GIL).
2. **Dispatcher Thread**: Running within the FastAPI main process, this thread reads from SharedMemory at 1Hz, calculates traffic deltas (KB/s) using previous snapshots, and resolves PIDs to application metadata via OS-native APIs (e.g., `iphlpapi.dll` on Windows, `lsof` on macOS).
3. **Data Propagation**: Computed snapshots are encoded using MsgPack to minimize payload size and broadcast to connected clients via Socket.io.
4. **OS Adapters**: Platform-specific bridges (Windows, macOS, Android) handle low-level operations such as process signaling, firewall rule injection, and VPN-based packet interception.

### Installation & Usage

#### Prerequisites
* **Windows**: Npcap installed in "WinPcap API-compatible mode".
* **macOS**: Libpcap (built-in).
* **Python**: 3.10+ and **Node.js**: 18+.

#### Backend Setup
1. Navigate to the `backend/` directory.
2. Create and activate a virtual environment: `python -m venv .venv`.
3. Install dependencies: `pip install -r requirements.txt`.
4. (Optional) Configure `INFLUXDB_TOKEN`, `SUPABASE_URL`, and `SUPABASE_KEY` environment variables.
5. Run the sentinel with elevated privileges:
   * **Windows**: `python main.py` (Run as Administrator).
   * **macOS**: `sudo python3 main.py`.

#### Frontend Setup
1. Navigate to the `frontend/` directory.
2. Install dependencies: `npm install`.
3. Start the development server: `npm run dev`.
4. Access the dashboard via `http://localhost:5173`.
