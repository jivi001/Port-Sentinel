/**
 * Sentinel — Socket Context Provider
 *
 * Creates a SINGLE Socket.IO connection and shares it across all pages
 * via React context. This prevents duplicate connections when navigating
 * between routes.
 */

import React, { createContext, useContext } from 'react';
import { useSocket } from './useSocket';

import type { PortTable, SparklinePoint } from '../types';

interface SocketContextValue {
  portTable: PortTable;
  sparklineData: Map<number, SparklinePoint[]>;
  connected: boolean;
  error: string | null;
}

const SocketContext = createContext<SocketContextValue>({
  portTable: [],
  sparklineData: new Map(),
  connected: false,
  error: null,
});

export const SocketProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const socketData = useSocket();

  return (
    <SocketContext.Provider value={socketData}>
      {children}
    </SocketContext.Provider>
  );
};

/**
 * Hook for pages to consume the shared socket data.
 * Replaces direct `useSocket()` calls in individual pages.
 */
export function useSocketContext(): SocketContextValue {
  return useContext(SocketContext);
}
