/**
 * Sentinel API Service
 * 
 * Centralized logic for all backend API interactions.
 * Optimized with dual-route discovery (Proxy -> Direct) to ensure 
 * control functions work regardless of dev-server configuration.
 */

import { BlockedPort, HealthResponse, PortTable } from '../types';

const DEV_BACKEND_URL = 'http://localhost:8600/api';
const PROXY_BASE = '/api';
const IS_DEV = import.meta.env.DEV;

export const apiService = {
  /**
   * Internal fetch wrapper with fallback logic.
   */
  _call: async (path: string, options: RequestInit = {}) => {
    const requestInit: RequestInit = {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    };

    const primaryBase = IS_DEV ? DEV_BACKEND_URL : PROXY_BASE;
    const secondaryBase = IS_DEV ? PROXY_BASE : DEV_BACKEND_URL;

    const doRequest = async (base: string, cors: boolean) => {
      const response = await fetch(`${base}${path}`, {
        ...requestInit,
        ...(cors ? { mode: 'cors' as RequestMode } : {}),
      });

      if (!response.ok) {
        if (base === PROXY_BASE && response.status === 404) {
          const contentType = response.headers.get('content-type') || '';
          if (!contentType.includes('application/json')) {
            throw new TypeError('Proxy unreachable');
          }
        }
        if (base === PROXY_BASE && response.status === 502) {
          throw new TypeError('Proxy unreachable');
        }
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      return response.json();
    };

    try {
      return await doRequest(primaryBase, primaryBase === DEV_BACKEND_URL);
    } catch (e: unknown) {
      const shouldFallback = e instanceof TypeError;
      if (!shouldFallback) throw e;
      console.warn(`[Sentinel API] Primary route failed for ${path}, trying fallback...`);
      return doRequest(secondaryBase, secondaryBase === DEV_BACKEND_URL);
    }
  },

  getHealth: async (): Promise<HealthResponse> => apiService._call('/health'),
  getBlockedPorts: async (): Promise<BlockedPort[]> => apiService._call('/blocked'),
  getPorts: async (): Promise<PortTable> => apiService._call('/ports'),
  getPortHistory: async (port: number, hours: number = 24): Promise<any[]> => 
    apiService._call(`/ports/${port}/history?hours=${hours}`),
  getAuditLogs: async (limit: number = 100): Promise<any[]> => 
    apiService._call(`/audit/logs?limit=${limit}`),
  getTopTalkers: async (hours: number = 24, limit: number = 10): Promise<any[]> => 
    apiService._call(`/analytics/top-talkers?hours=${hours}&limit=${limit}`),

  killProcess: async (pid: number): Promise<boolean> => {
    const res = await apiService._call(`/control/kill/${pid}`, { method: 'POST' });
    return !!res.success;
  },

  blockPort: async (port: number, protocol: string = 'TCP'): Promise<boolean> => {
    const res = await apiService._call(`/control/block/${port}?protocol=${protocol}`, { method: 'POST' });
    return !!res.success;
  },

  unblockPort: async (port: number): Promise<boolean> => {
    const res = await apiService._call(`/control/unblock/${port}`, { method: 'POST' });
    return !!res.success;
  },

  suspendProcess: async (pid: number): Promise<boolean> => {
    const res = await apiService._call(`/control/suspend/${pid}`, { method: 'POST' });
    return !!res.success;
  },

  resumeProcess: async (pid: number): Promise<boolean> => {
    const res = await apiService._call(`/control/resume/${pid}`, { method: 'POST' });
    return !!res.success;
  },
};
