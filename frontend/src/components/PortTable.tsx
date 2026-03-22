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
    <div className="port-table-header">
      <div className="port-col-port">PORT</div>
      <div className="port-col-proto">PROTO</div>
      <div className="port-col-app">APPLICATION & PID</div>
      <div className="port-col-endpoint">REMOTE ENDPOINT</div>
      <div className="port-col-traffic">IN</div>
      <div className="port-col-traffic">OUT</div>
      <div className="port-col-traffic">TOTAL</div>
      <div className="port-col-risk">RISK</div>
      <div className="port-col-trend">TREND</div>
    </div>
  );

  if (filtered.length === 0) {
    return (
      <div className="port-table-container">
        {renderHeader()}
        <div className="empty-state" style={{ padding: '80px 0' }}>
          <div className="empty-state__icon">📡</div>
          <div className="empty-state__text" style={{ fontSize: '1rem', fontWeight: 600 }}>
            {filter ? 'NO MATCHING PORTS FOUND' : 'AWAITING NETWORK TRAFFIC...'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="port-table-container">
      {renderHeader()}

      <div ref={parentRef} className="port-table-body">
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
                key={entry.port}
                className={`port-row ${isHighRisk ? 'port-row--high-risk' : ''}`}
                style={{
                  position: 'absolute',
                  top: 0, left: 0, width: '100%',
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <div className="port-col-port port-row__port">{entry.port}</div>
                <div className="port-col-proto port-row__proto">{entry.protocol}</div>
                
                <div className="port-col-app">
                  <div className="port-row__app-name" title={entry.app_name}>
                    {entry.app_name}
                  </div>
                  <div className="port-row__pid-sub">
                    PID: {entry.pid}
                  </div>
                </div>

                <div className="port-col-endpoint">
                  <div className="port-row__ip" title={entry.remote_ip}>
                    {entry.remote_ip === "0.0.0.0" ? "—" : entry.remote_ip}
                  </div>
                  <div className="port-row__org-sub" title={entry.org}>
                    {entry.org !== "Unknown" ? entry.org : ""}
                  </div>
                </div>

                <div className="port-col-traffic port-row__bytes port-row__bytes--in">
                  {formatKb(entry.kb_s_in)}
                </div>
                <div className="port-col-traffic port-row__bytes port-row__bytes--out">
                  {formatKb(entry.kb_s_out)}
                </div>
                <div className="port-col-traffic port-row__bytes port-row__bytes--total">
                  {formatKb((entry.kb_s_in ?? 0) + (entry.kb_s_out ?? 0))}
                </div>

                <div className="port-col-risk" style={{ textAlign: 'center' }}>
                  <span className={`risk-indicator risk-indicator--${risk >= 10 ? 'critical' : risk >= 5 ? 'warning' : 'safe'}`}>
                    {risk >= 10 ? 'CRITICAL' : risk >= 5 ? 'WARNING' : 'SECURE'}
                  </span>
                </div>

                <div className="port-col-trend">
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
