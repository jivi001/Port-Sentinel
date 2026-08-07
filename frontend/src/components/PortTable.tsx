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
  
  const [sortKey, setSortKey] = React.useState<keyof PortTableType[0] | null>(null);
  const [sortDir, setSortDir] = React.useState<'asc' | 'desc'>('asc');
  const [contextMenuOpenId, setContextMenuOpenId] = React.useState<string | null>(null);

  const handleSort = (key: keyof PortTableType[0]) => {
    if (sortKey === key) {
      if (sortDir === 'asc') setSortDir('desc');
      else setSortKey(null);
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const filteredAndSorted = useMemo(() => {
    let result = data;
    if (filter) {
      const q = filter.toLowerCase();
      result = data.filter(
        (e) =>
          String(e.port).includes(q) ||
          e.app_name.toLowerCase().includes(q) ||
          String(e.pid).includes(q) ||
          e.protocol.toLowerCase().includes(q) ||
          e.remote_ip.includes(q) ||
          e.org.toLowerCase().includes(q)
      );
    }
    
    if (sortKey) {
      result = [...result].sort((a, b) => {
        const valA = a[sortKey];
        const valB = b[sortKey];
        if (valA == null) return 1;
        if (valB == null) return -1;
        if (valA < valB) return sortDir === 'asc' ? -1 : 1;
        if (valA > valB) return sortDir === 'asc' ? 1 : -1;
        return 0;
      });
    }
    return result;
  }, [data, filter, sortKey, sortDir]);

  const virtualizer = useVirtualizer({
    count: filteredAndSorted.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ROW_HEIGHT,
    overscan: 10,
  });

  const renderSortIcon = (key: keyof PortTableType[0]) => {
    if (sortKey !== key) return null;
    return sortDir === 'asc' ? ' ↑' : ' ↓';
  };

  const renderHeader = () => (
    <div className="port-table-header">
      <div className="port-col-port" onClick={() => handleSort('port')} style={{ cursor: 'pointer' }}>PORT{renderSortIcon('port')}</div>
      <div className="port-col-proto" onClick={() => handleSort('protocol')} style={{ cursor: 'pointer' }}>PROTO{renderSortIcon('protocol')}</div>
      <div className="port-col-app" onClick={() => handleSort('app_name')} style={{ cursor: 'pointer' }}>APPLICATION & PID{renderSortIcon('app_name')}</div>
      <div className="port-col-endpoint" onClick={() => handleSort('remote_ip')} style={{ cursor: 'pointer' }}>REMOTE ENDPOINT{renderSortIcon('remote_ip')}</div>
      <div className="port-col-traffic" onClick={() => handleSort('kb_s_in')} style={{ cursor: 'pointer' }}>IN{renderSortIcon('kb_s_in')}</div>
      <div className="port-col-traffic" onClick={() => handleSort('kb_s_out')} style={{ cursor: 'pointer' }}>OUT{renderSortIcon('kb_s_out')}</div>
      <div className="port-col-traffic">TOTAL</div>
      <div className="port-col-risk" onClick={() => handleSort('risk_score')} style={{ cursor: 'pointer' }}>RISK{renderSortIcon('risk_score')}</div>
      <div className="port-col-trend">TREND</div>
      <div style={{ width: '40px' }} />
    </div>
  );

  if (filteredAndSorted.length === 0) {
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
            const entry = filteredAndSorted[virtualRow.index];
            const sparkline = sparklineData.get(entry.port) || [];
            const risk = entry.risk_score ?? 0;
            const isHighRisk = risk >= 7;
            const rowId = `${entry.protocol}-${entry.port}-${entry.pid}`;

            return (
              <div
                key={rowId}
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
                
                <div style={{ width: '40px', display: 'flex', justifyContent: 'flex-end', position: 'relative' }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setContextMenuOpenId(contextMenuOpenId === rowId ? null : rowId);
                      }}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
                    >
                      ⋮
                    </button>
                    
                    {contextMenuOpenId === rowId && (
                      <div 
                        style={{
                          position: 'absolute', top: '100%', right: '10px', zIndex: 100,
                          background: 'var(--bg-secondary)', border: '1px solid var(--border-dim)',
                          borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-md)',
                          minWidth: '150px', padding: '4px 0', overflow: 'hidden'
                        }}
                      >
                        <div
                            onClick={(e) => {
                              e.stopPropagation();
                              setContextMenuOpenId(null);
                            }}
                            className="context-menu-item context-menu-item--danger"
                            style={{ padding: '8px 16px', fontSize: '0.8rem', cursor: 'pointer', color: 'var(--accent-red)' }}
                          >
                            Block Port {entry.port}
                        </div>
                        <div
                            onClick={(e) => {
                              e.stopPropagation();
                              setContextMenuOpenId(null);
                            }}
                            className="context-menu-item"
                            style={{ padding: '8px 16px', fontSize: '0.8rem', cursor: 'pointer', color: 'var(--text-primary)' }}
                          >
                            Kill PID {entry.pid}
                        </div>
                      </div>
                    )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
      {/* Click outside to close context menu */}
      {contextMenuOpenId && (
        <div 
          onClick={() => setContextMenuOpenId(null)}
          style={{ position: 'fixed', inset: 0, zIndex: 99 }} 
        />
      )}
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
