/**
 * Sentinel — PortTable Component
 *
 * Virtualised port list using @tanstack/react-virtual.
 * Each row shows port, protocol, app name, PID, in/out/total KB/s, and sparkline.
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

const ROW_HEIGHT = 42;

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
        e.protocol.toLowerCase().includes(q),
    );
  }, [data, filter]);

  const virtualizer = useVirtualizer({
    count: filtered.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  if (filtered.length === 0) {
    return (
      <div className="port-table-container">
        <div className="port-table-header">
          <span>Port</span><span>Proto</span><span>Application</span>
          <span>PID</span><span style={{ textAlign: 'right' }}>In</span>
          <span style={{ textAlign: 'right' }}>Out</span>
          <span style={{ textAlign: 'right' }}>Total</span><span>Trend</span>
        </div>
        <div className="empty-state" style={{ padding: '64px 0' }}>
          <div className="empty-state__icon">📡</div>
          <div className="empty-state__text">
            {filter ? 'No ports match your filter' : 'Waiting for traffic data…'}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="port-table-container">
      <div className="port-table-header">
        <span>Port</span><span>Proto</span><span>Application</span>
        <span>PID</span><span style={{ textAlign: 'right' }}>In</span>
        <span style={{ textAlign: 'right' }}>Out</span>
        <span style={{ textAlign: 'right' }}>Total</span><span>Trend</span>
      </div>

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

            return (
              <div
                key={entry.port}
                className="port-row"
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  width: '100%',
                  height: `${virtualRow.size}px`,
                  transform: `translateY(${virtualRow.start}px)`,
                }}
              >
                <span className="port-row__port">{entry.port}</span>
                <span className="port-row__proto">{entry.protocol}</span>
                <span className="port-row__app" title={entry.app_name}>{entry.app_name}</span>
                <span className="port-row__pid">{entry.pid}</span>
                <span className="port-row__bytes port-row__bytes--in">
                  {formatKb(entry.kb_s_in)}
                </span>
                <span className="port-row__bytes port-row__bytes--out">
                  {formatKb(entry.kb_s_out)}
                </span>
                <span className="port-row__bytes port-row__bytes--total">
                  {formatKb((entry.kb_s_in ?? 0) + (entry.kb_s_out ?? 0))}
                </span>
                <SparklineChart data={sparkline} />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

/** Format KB/s value: 0 → "—", <0.1 → "<0.1", else 1 decimal */
function formatKb(val: number | undefined): string {
  if (val == null || val === 0) return '—';
  if (val < 0.1) return '<0.1';
  if (val >= 1024) return `${(val / 1024).toFixed(1)} M`;
  return val.toFixed(1);
}

export default React.memo(PortTable);
