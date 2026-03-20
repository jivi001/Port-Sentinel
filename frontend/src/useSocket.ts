/**
 * Sentinel Frontend — Socket.io Hook
 *
 * Connects to ws://localhost:8600, decodes MsgPack port_table events,
 * and provides a live PortTable state.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { decode } from '@msgpack/msgpack';
import type { PortTable, SparklinePoint } from './types';

const SOCKET_URL = '/';
const SPARKLINE_WINDOW = 60; // 60 seconds of history

interface UseSocketReturn {
  portTable: PortTable;
  sparklineData: Map<number, SparklinePoint[]>;
  connected: boolean;
  error: string | null;
}

export function useSocket(): UseSocketReturn {
  const [portTable, setPortTable] = useState<PortTable>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sparklineRef = useRef<Map<number, SparklinePoint[]>>(new Map());
  const [, setSparklineVersion] = useState(0);
  const socketRef = useRef<Socket | null>(null);

  const processPortTable = useCallback((data: PortTable) => {
    const now = Date.now() / 1000;
    const map = sparklineRef.current;

    for (const entry of data) {
      const points = map.get(entry.port) || [];

      points.push({
        t: now,
        kbIn: entry.kb_s_in,
        kbOut: entry.kb_s_out,
      });

      // Evict points older than SPARKLINE_WINDOW
      const cutoff = now - SPARKLINE_WINDOW;
      const firstValid = points.findIndex(p => p.t >= cutoff);
      if (firstValid > 0) {
        points.splice(0, firstValid);
      }

      map.set(entry.port, points);
    }

    // Evict ports not in the current table
    const activePorts = new Set(data.map(e => e.port));
    for (const port of map.keys()) {
      if (!activePorts.has(port)) {
        map.delete(port);
      }
    }

    setPortTable(data);
    setSparklineVersion(v => v + 1);
  }, []);

  useEffect(() => {
    const socket = io(SOCKET_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: Infinity,
    });

    socketRef.current = socket;

    socket.on('connect', () => {
      setConnected(true);
      setError(null);
    });

    socket.on('disconnect', () => {
      setConnected(false);
    });

    socket.on('connect_error', (err: Error) => {
      setError(`Connection error: ${err.message}`);
    });

    socket.on('port_table', (raw: ArrayBuffer | Uint8Array) => {
      try {
        const decoded = decode(raw instanceof Uint8Array ? raw : new Uint8Array(raw)) as PortTable;
        processPortTable(decoded);
      } catch (e) {
        console.error('MsgPack decode error:', e);
      }
    });

    return () => {
      socket.disconnect();
    };
  }, [processPortTable]);

  return {
    portTable,
    sparklineData: sparklineRef.current,
    connected,
    error,
  };
}
