/**
 * Vigilant Frontend — TypeScript Types
 */

/** Single port entry in the port table emitted at 1Hz */
export interface PortEntry {
  port: number;
  pid: number;
  app_name: string;
  protocol: string;   // "TCP" | "UDP"
  kb_s_in: number;    // KB/s inbound
  kb_s_out: number;   // KB/s outbound
  kb_s: number;       // Total KB/s
  direction: string;  // "IN" | "OUT" | "BOTH"
  status: string;     // "LISTEN" | "ESTABLISHED" | etc.
  risk_score: number; // Threat score 0-10
  remote_ip: string;
  org: string;
  country: string;
  timestamp: number;  // epoch
}

/** Port table sent via Socket.io */
export type PortTable = PortEntry[];

/** Sparkline data point */
export interface SparklinePoint {
  t: number;       // timestamp
  kbIn: number;
  kbOut: number;
}

/** Control action types — no process termination */
export type ControlAction = "request_approval" | "block" | "unblock";

/** API response for control actions */
export interface ControlResponse {
  success: boolean;
  pid?: number;
  port?: number;
  action: ControlAction;
}

/** Health check response */
export interface HealthResponse {
  status: string;
  product: string;
  version: string;
  platform: string;
  sniffer_alive: boolean;
  ports_tracked: number;
  uptime_seconds: number;
}

/** Blocked port record */
export interface BlockedPort {
  port: number;
  block_type: string;
  blocked_at: number;
  reason: string;
}

/** Analyst approval record */
export interface AnalystApproval {
  id: number;
  created_at: number;
  action_type: string;
  target_identifier: string;
  reason: string;
  status: "pending" | "approved" | "rejected";
  risk_score: number;
}

/** Audit log entry */
export interface AuditLogEntry {
  id: number;
  timestamp: number;
  event_type: string;
  app_name: string | null;
  port: number | null;
  pid: number | null;
  severity: string;
  message: string;
  details: string | null;
}

/** Geo threat data for globe visualization */
export interface GeoThreatEntry {
  ip: string;
  port: number;
  app_name: string;
  country: string;
  org: string;
  risk_score: number;
  kb_s_in: number;
  kb_s_out: number;
  protocol: string;
  lat?: number;
  lng?: number;
}

/** Country-level threat statistics */
export interface CountryStats {
  country: string;
  connections: number;
  total_risk: number;
  total_kb_s: number;
}

/** Dashboard layout item */
export interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
}
