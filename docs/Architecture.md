# SentientShield AI Architecture

## 1. High-Level Overview
SentientShield AI is an enterprise-ready, cross-platform active network traffic analyzer and autonomous response system. The core architecture uses an adaptive plug-and-play model where specialized modules handle packet analysis, heuristic drift detection, cross-platform OS administration, and Analyst Approval workflows.

## 2. Components
### 2.1 OSBridgeAdapter (Platform Abstraction)
A unified interface resolving OS-specific metrics (Windows, macOS, Linux). It dynamically loads the correct adapter (`win32_bridge`, `linux_bridge`, `darwin_bridge`) to retrieve network statistics, PID mapping, and perform sanctioned process interactions.

### 2.2 SQLAlchemy / JWT Backend
The backend utilizes SQLAlchemy with SQLite/PostgreSQL support. Crucially, all autonomous response (process suspension/termination) requests are intercepted by the Analyst Approval workflow and persisted in the `AnalystApproval` table, protecting against automated disruption of critical business systems.

### 2.3 React / Tailwind Frontend
The "Single Pane of Glass" frontend is built with React, Vite, and Tailwind CSS (v4), featuring an enterprise "Cyber Midnight" aesthetic. 
- **Dashboard:** Uses `react-grid-layout` for real-time customizable widgets and `recharts` for throughput visualization.
- **Topology:** Integrates `react-globe.gl` for a 3D visualization of geographic attack paths.
- **Approval Queue:** Allows security analysts to authorize or deny drift detection actions.

## 3. Communication Protocol
- **WebSockets:** Real-time port metrics and threat updates are multiplexed over a Socket.IO connection and encoded via MsgPack for high-throughput efficiency.
- **RESTful API:** Configuration, JWT authentication, and historical Analyst Approvals are managed via standard REST endpoints protected by Bearer token authorization.
