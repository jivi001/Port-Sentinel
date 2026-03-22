/**
 * Sentinel — Professional Forensics Page
 */

import React, { useState, useCallback, useEffect } from 'react';
import { AreaChart, Area, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts';
import { useSocketContext } from '../hooks/SocketContext';
import { apiService } from '../services/apiService';

const TIME_RANGES = [
  { label: '1H', hours: 1 },
  { label: '6H', hours: 6 },
  { label: '24H', hours: 24 },
];

const HistoricalLogsPage: React.FC = () => {
  const { portTable } = useSocketContext();
  const [selectedPort, setSelectedPort] = useState<number | null>(null);
  const [selectedRange, setSelectedRange] = useState(1);
  const [history, setHistory] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchHistory = useCallback(async () => {
    if (selectedPort == null) return;
    setLoading(true);
    try {
      const data = await apiService.getPortHistory(selectedPort, selectedRange);
      setHistory(data);
    } catch (e) {
      console.error(e);
    } finally { setLoading(false); }
  }, [selectedPort, selectedRange]);

  const fetchAuditLogs = useCallback(async () => {
    try {
      const data = await apiService.getAuditLogs(50);
      setAuditLogs(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    fetchAuditLogs();
    if (selectedPort != null) fetchHistory();
  }, [selectedPort, selectedRange, fetchHistory, fetchAuditLogs]);

  return (
    <div className="page-container">
      <header className="page-header">
        <h1 className="page-title">Forensic Analysis</h1>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
          <div className="btn-group">
            {TIME_RANGES.map((r) => (
              <button 
                key={r.hours} 
                className={`btn ${selectedRange === r.hours ? 'btn--active' : ''}`}
                onClick={() => setSelectedRange(r.hours)}
              >{r.label}</button>
            ))}
          </div>
          <select 
            className="btn" 
            style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-default)', color: 'white' }}
            value={selectedPort ?? ''} 
            onChange={(e) => setSelectedPort(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">SELECT PORT...</option>
            {[...new Set(portTable.map(p => p.port))].sort((a,b) => a-b).map(p => <option key={p} value={p}>{p}</option>)}
          </select>
        </div>
      </header>

      {/* Traffic Visualization */}
      {selectedPort && history.length > 0 && (
        <section className="sentinel-section">
          <div className="sentinel-section__header">
            <h2 className="sentinel-section__title">Port {selectedPort} Throughput</h2>
          </div>
          <div style={{ width: '100%', height: 200, padding: '20px' }}>
            <ResponsiveContainer>
              <AreaChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border-dim)" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis hide />
                <Tooltip contentStyle={{ background: 'var(--bg-secondary)', border: 'none', borderRadius: '8px' }} />
                <Area type="monotone" dataKey="kb_s_in" stroke="var(--accent-blue)" fill="var(--accent-blue)" fillOpacity={0.1} isAnimationActive={false} />
                <Area type="monotone" dataKey="kb_s_out" stroke="var(--accent-orange)" fill="var(--accent-orange)" fillOpacity={0.1} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Audit Logs */}
      <section className="sentinel-section" style={{ flex: 1, minHeight: 0 }}>
        <div className="sentinel-section__header">
          <h2 className="sentinel-section__title">Security Events Audit</h2>
          <button className="btn" onClick={fetchAuditLogs}>REFRESH_LOGS</button>
        </div>
        <div className="data-table-container">
          <div className="data-table-header">
            <div className="col-md">TIMESTAMP</div>
            <div className="col-md">EVENT</div>
            <div className="col-lg">TARGET</div>
            <div className="col-sm">SEVERITY</div>
            <div className="col-flex">MESSAGE</div>
          </div>
          <div className="data-table-body">
            {auditLogs.length === 0 ? (
              <div style={{ padding: '60px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>NO SECURITY EVENTS DETECTED</div>
            ) : (
              auditLogs.map((log) => (
                <div key={log.id} className="data-row">
                  <div className="col-md mono text-muted" style={{ fontSize: '0.7rem' }}>{new Date(log.timestamp * 1000).toLocaleTimeString()}</div>
                  <div className="col-md mono text-blue" style={{ fontSize: '0.7rem' }}>{log.event_type.toUpperCase()}</div>
                  <div className="col-lg mono" style={{ fontSize: '0.8rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{log.app_name || `PORT ${log.port}`}</div>
                  <div className="col-sm mono" style={{ color: log.severity === 'critical' ? 'var(--accent-red)' : 'var(--accent-orange)', fontSize: '0.7rem' }}>{log.severity.toUpperCase()}</div>
                  <div className="col-flex" style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{log.message}</div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>
    </div>
  );
};

export default HistoricalLogsPage;
