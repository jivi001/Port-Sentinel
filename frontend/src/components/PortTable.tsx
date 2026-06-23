/**
 * Sentinel — Professional PortTable
 * 
 * Optimized for alignment, readability, and information density.
 */

import React, { useRef, useMemo } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { PortTable as PortTableType, SparklinePoint } from '../types';
import SparklineChart from './SparklineChart';

interface PortTableProps {
  data: PortTableType;
  sparklineData: Map<number, SparklinePoint[]>;
  filter: string;
}

const ROW_HEIGHT = 48; // Increased for better multi-line legibility

const PortTable: React.FC<PortTableProps> = ({ data, sparklineData, filter }) => {
  const parentRef = useRef<HTMLDivElement>(null);

  const filtered = useMemo(() => {
    if (!filter) return data;
    const q = filter.toLowerCase();
    return data.filter(
      (e) =>
        String(e.port).includes(q) ||
        e.app_name.toLowerCase().includes(q) ||
        String(e.pid).includes(q) ||
        e.protocol.toLowerCase().includes(q) ||
        e.remote_ip.includes(q) ||
        e.org.toLowerCase().includes(q)
    );
  }, [data, filter]);

  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  const renderHeader = () => (
    <div className="grid grid-cols-[80px_80px_1.5fr_2fr_100px_100px_100px_120px_150px] gap-4 items-center px-6 py-4 bg-secondary/50 border-b border-border-main text-xs font-bold text-text-muted uppercase tracking-widest sticky top-0 z-10">
      <div>PORT</div>
      <div>PROTO</div>
      <div>APPLICATION & PID</div>
      <div>REMOTE ENDPOINT</div>
      <div className="text-right">IN</div>
      <div className="text-right">OUT</div>
      <div className="text-right">TOTAL</div>
      <div className="text-center">RISK</div>
      <div className="text-right">TREND</div>
    </div>
  );

  if (filtered.length === 0) {
    return (
      <div className="flex flex-col w-full h-full bg-surface border border-border-main rounded-xl shadow-lg overflow-hidden">
        {renderHeader()}
        <div className="flex flex-col items-center justify-center flex-1 py-20 text-center">
          <div className="text-4xl mb-4 opacity-50">📡</div>
          <div className="text-text-muted text-sm font-bold tracking-widest">
            {filter ? 'NO MATCHING PORTS FOUND' : 'AWAITING NETWORK TRAFFIC...'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col w-full h-full bg-surface border border-border-main rounded-xl shadow-lg overflow-hidden">
      {renderHeader()}

      <div ref={parentRef} className="flex-1 overflow-auto">
        <div
          style={{
            height: `${virtualizer.getTotalSize()}px`,
            width: '100%',
            position: 'relative',
          }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const entry = filtered[virtualRow.index];
            const sparkline = sparklineData.get(entry.port) || [];
            const risk = entry.risk_score ?? 0;
            const isHighRisk = risk >= 7;

            return (
              <div
                key={`${entry.protocol}-${entry.port}-${entry.pid}`}
                className={`grid grid-cols-[80px_80px_1.5fr_2fr_100px_100px_100px_120px_150px] gap-4 items-center px-6 border-b border-border-main/50 hover:bg-hover transition-colors group ${isHighRisk ? 'bg-danger/5 hover:bg-danger/10' : ''}`}
                style={{
                  position: 'absolute',
                  top: 0, left: 0, width: '100%',
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <div className="font-mono text-sm font-bold text-text-main">{entry.port}</div>
                <div className="font-mono text-xs text-primary bg-primary/10 px-2 py-1 rounded w-fit">{entry.protocol}</div>
                
                <div className="min-w-0 pr-4">
                  <div className="font-bold text-sm text-text-main truncate" title={entry.app_name}>
                    {entry.app_name}
                  </div>
                  <div className="font-mono text-xs text-text-muted mt-0.5">
                    PID: {entry.pid}
                  </div>
                </div>

                <div className="min-w-0 pr-4">
                  <div className="font-mono text-sm text-text-main truncate" title={entry.remote_ip}>
                    {entry.remote_ip === "0.0.0.0" ? "—" : entry.remote_ip}
                  </div>
                  <div className="text-xs text-text-muted mt-0.5 truncate" title={entry.org}>
                    {entry.org !== "Unknown" ? entry.org : ""}
                  </div>
                </div>

                <div className="font-mono text-sm text-primary text-right">{formatKb(entry.kb_s_in)}</div>
                <div className="font-mono text-sm text-warning text-right">{formatKb(entry.kb_s_out)}</div>
                <div className="font-mono text-sm font-bold text-text-main text-right">
                  {formatKb((entry.kb_s_in ?? 0) + (entry.kb_s_out ?? 0))}
                </div>

                <div className="text-center">
                  <span className={`px-2.5 py-1 rounded-full text-[10px] font-bold tracking-wider ${
                    risk >= 10 ? 'bg-danger/20 text-danger border border-danger/30' : 
                    risk >= 5 ? 'bg-warning/20 text-warning border border-warning/30' : 
                    'bg-accent/20 text-accent border border-accent/30'
                  }`}>
                    {risk >= 10 ? 'CRITICAL' : risk >= 5 ? 'WARNING' : 'SECURE'}
                  </span>
                </div>

                <div className="h-8 w-full opacity-70 group-hover:opacity-100 transition-opacity">
                  <SparklineChart data={sparkline} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

function formatKb(val: number | undefined): string {
  if (val == null || val === 0) return '—';
  if (val < 0.1) return '<0.1';
  if (val >= 1024) return `${(val / 1024).toFixed(1)}M`;
  return val.toFixed(1);
}

export default React.memo(PortTable);
