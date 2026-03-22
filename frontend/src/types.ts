/**
 * Sentinel Frontend — TypeScript Types
 */

/** Single port entry in the port table emitted at 1Hz */
export interface PortEntry {
  port: number;
  pid: number;
  app_name: string;
  protocol: string;   // "TCP" | "UDP"
  kb_s_in: number;    // KB/s inbound
  kb_s_out: number;   // KB/s outbound
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

/** Control action types */
export type ControlAction = "suspend" | "resume" | "kill" | "block" | "unblock";

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
  platform: string;
  sniffer_alive: boolean;
  ports_tracked: number;
  uptime_seconds: number;
}

/** Blocked port record */
export interface BlockedPort {
  port: number;
  block_type: string;
  reason: string;
  created_at: string;
}
