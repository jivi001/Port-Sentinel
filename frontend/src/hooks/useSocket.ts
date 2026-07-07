/**
 * Sentinel Frontend — Socket.io Hook
 *
 * Connects to ws://localhost:8600, decodes MsgPack port_table events,
 * and provides a live PortTable state.
 */

import { useEffect, useState, useCallback } from 'react';
import { io } from 'socket.io-client';
import { decode } from '@msgpack/msgpack';
import { z } from 'zod';
import type { PortTable } from '../types';

const PortEntrySchema = z.object({
  port: z.number(),
  pid: z.number(),
  app_name: z.string(),
  protocol: z.string(),
  kb_s_in: z.number(),
  kb_s_out: z.number(),
  kb_s: z.number(),
  direction: z.string().optional(),
  status: z.string().optional(),
  risk_score: z.number(),
  remote_ip: z.string(),
  org: z.string(),
  country: z.string(),
  timestamp: z.number(),
});

const PortTableSchema = z.array(PortEntrySchema);

const SOCKET_URL = import.meta.env.DEV ? 'http://localhost:8600' : '/';

interface UseSocketReturn {
  portTable: PortTable;
  connected: boolean;
  error: string | null;
}

export function useSocket(): UseSocketReturn {
  const [portTable, setPortTable] = useState<PortTable>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const processPortTable = useCallback((data: PortTable) => {
    setPortTable(data);
  }, []);

  useEffect(() => {
    const socket = io(SOCKET_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionAttempts: Infinity,
    });



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
        const decoded = decode(raw instanceof Uint8Array ? raw : new Uint8Array(raw));
        const validated = PortTableSchema.parse(decoded) as PortTable;
        processPortTable(validated);
      } catch (e: any) {
        if (e instanceof z.ZodError) {
          console.error('Socket.io payload validation failed:', e.issues);
        } else {
          console.error('MsgPack decode error:', e);
        }
      }
    });

    return () => {
      socket.disconnect();
    };
  }, [processPortTable]);

  return {
    portTable,
    connected,
    error,
  };
}
