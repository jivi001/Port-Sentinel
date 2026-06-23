# Vigilant REST & WebSocket API Specification

This document details the REST endpoints and WebSocket protocols exposed by the Vigilant backend server.

---

## 1. Authentication & Session Flow

The Vigilant API uses **JSON Web Tokens (JWT)** for session authentication.

### Login Flow
1. Send a POST request to `/api/auth/login` containing `username` and `password` as url-encoded form data.
2. The endpoint returns a JSON payload containing the `access_token` and `token_type`.
3. For subsequent authenticated endpoints, attach the token to the HTTP header as a Bearer token:
   ```http
   Authorization: Bearer <your_access_token>
   ```

---

## 2. API Endpoints

All API endpoints are prefixed with `/api`.

### 2.1 Authentication & Profile

#### `POST /api/auth/login`
- **Request Format:** Form-urlencoded (`username`, `password`)
- **Response Schema:**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer"
  }
  ```

#### `GET /api/auth/me`
- **Authentication:** Required (Bearer)
- **Response Schema:**
  ```json
  {
    "username": "admin",
    "email": "admin@vigilant.local",
    "role": "admin"
  }
  ```

#### `GET /api/auth/preferences`
- **Authentication:** Required (Bearer)
- **Response Schema:** Returns the user preference key-value pairs stored in the database.

#### `POST /api/auth/preferences`
- **Authentication:** Required (Bearer)
- **Request Body:** JSON dictionary of preferences (e.g. `{"theme": "light", "refresh_speed": "normal"}`)
- **Response Schema:** `{"success": true}`

---

### 2.2 Network Ports & Traffic

#### `GET /api/ports`
- **Authentication:** Required (Bearer)
- **Response Schema:**
  ```json
  [
    {
      "port": 443,
      "pid": 1124,
      "app_name": "chrome.exe",
      "protocol": "TCP",
      "kb_s_in": 12.4,
      "kb_s_out": 3.8,
      "risk_score": 0,
      "remote_ip": "104.244.42.1",
      "org": "Twitter, Inc.",
      "country": "US",
      "timestamp": 1729004052.1
    }
  ]
  ```

#### `GET /api/ports/{port}/history`
- **Authentication:** Required (Bearer)
- **Query Parameters:** `hours` (int, default=24)
- **Response Schema:** Time-series array of traffic metrics captured for the specified port.

---

### 2.3 Mitigation Control

#### `POST /api/control/block/{port}`
- **Authentication:** Required (Bearer)
- **Query Parameters:** `protocol` (string, default="TCP")
- **Response Schema:**
  ```json
  {
    "success": true,
    "message": "Blocked port 443 (TCP)"
  }
  ```

#### `POST /api/control/unblock/{port}`
- **Authentication:** Required (Bearer)
- **Response Schema:**
  ```json
  {
    "success": true,
    "message": "Unblocked port 443"
  }
  ```

#### `GET /api/blocked`
- **Authentication:** Required (Bearer)
- **Response Schema:** List of ports currently blocked by Vigilant.

---

### 2.4 Analyst Approval Workflow

#### `POST /api/approvals/request`
- **Authentication:** Required (Bearer)
- **Query Parameters:**
  - `pid` (int, required)
  - `app_name` (string, optional)
  - `reason` (string, optional)
- **Response Schema:**
  ```json
  {
    "success": true,
    "approval_id": 4,
    "status": "pending",
    "message": "Process suspension ticket queued for PID 1124."
  }
  ```

#### `GET /api/approvals`
- **Authentication:** Required (Bearer)
- **Response Schema:** List of all pending, approved, and rejected process tickets.

#### `POST /api/approvals/{id}/resolve`
- **Authentication:** Required (Bearer)
- **Request Body:**
  ```json
  {
    "status": "approved" // or "rejected"
  }
  ```
- **Response Schema:** `{"success": true, "message": "Approval ticket 4 resolved as approved."}`

---

### 2.5 Analytics & Auditing

#### `GET /api/analytics/top-talkers`
- **Authentication:** Required (Bearer)
- **Query Parameters:** `hours` (int, default=24), `limit` (int, default=10)
- **Response Schema:** Displays the top bandwidth-consuming applications.

#### `GET /api/audit/logs`
- **Authentication:** Required (Bearer)
- **Query Parameters:** `limit` (int, default=100)
- **Response Schema:** List of system audit logs showing admin actions and policy executions.

---

### 2.6 Threat Intelligence & Geolocation

#### `GET /api/threats/geo`
- **Query Parameters:** `min_risk` (int, default=0)
- **Response Schema:**
  ```json
  [
    {
      "ip": "185.220.101.5",
      "city": "Berlin",
      "country": "DE",
      "latitude": 52.52,
      "longitude": 13.405,
      "risk": 8,
      "org": "Tor Exit Node",
      "port": 443
    }
  ]
  ```

#### `GET /api/threats/countries`
- **Response Schema:** Threat count aggregates grouped by country (e.g. `[{"country": "DE", "count": 2}]`).

#### `GET /api/threats/timeline`
- **Response Schema:** Historical buckets of threats for replay animation.

---

## 3. WebSockets & Real-time Feeds

Vigilant streams high-frequency updates via Socket.IO connection at `/`.

### Connection
- **Endpoint:** `ws://127.0.0.1:8600/` or proxied through frontend.
- **Transports:** `['websocket', 'polling']`

### Events

#### Emit: `port_table`
Sent by the backend server every 1 second.
- **Payload Format:** **MsgPack Binary Buffer**
- **Decoded Array Format:**
  An array of arrays (tuple rows) to reduce bandwidth footprint:
  ```typescript
  [
    [
      port: number,
      bytes_in: number,
      bytes_out: number,
      pid: number,
      protocol: number, // 0 = TCP, 1 = UDP
      active: number,   // 0 = false, 1 = true
      risk_score: number,
      remote_ip: string
    ]
  ]
  ```
