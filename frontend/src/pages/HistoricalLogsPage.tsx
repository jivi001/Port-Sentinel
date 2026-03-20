/**
 * Sentinel — Historical Logs Page
 *
 * Time range selector, port filter, traffic history chart,
 * and data table for historical traffic entries.
 */

import React, { useState, useCallback, useEffect } from 'react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { useSocketContext } from '../SocketContext';

interface HistoryEntry {
  id: number;
  timestamp: number;
  port: number;
  pid: number;
  app_name: string;
  kb_s_in: number;
  kb_s_out: number;
  protocol: string;
  direction: string;
}

const TIME_RANGES = [
  { label: '1h', hours: 1 },
  { label: '6h', hours: 6 },
  { label: '24h', hours: 24 },
];

const HistoricalLogsPage: React.FC = () => {
  const { portTable, connected } = useSocketContext();
  const [selectedPort, setSelectedPort] = useState<number | null>(null);
  const [selectedRange, setSelectedRange] = useState(1);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  /* Get unique ports from live data */
  const availablePorts = React.useMemo(() => {
    const ports = [...new Set(portTable.map((e) => e.port))];
    return ports.sort((a, b) => a - b);
  }, [portTable]);

  /* Fetch history for selected port */
  const fetchHistory = useCallback(async () => {
    if (selectedPort == null) return;
    setLoading(true);
    setFetchError(null);
    try {
      const resp = await fetch(
        `/api/ports/${selectedPort}/history?hours=${selectedRange}`
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setHistory(Array.isArray(data) ? data : []);
    } catch (e) {
      setFetchError(`Failed to fetch history: ${String(e)}`);
      setHistory([]);
    } finally {
      setLoading(false);
    }
  }, [selectedPort, selectedRange]);

  useEffect(() => {
    if (selectedPort != null) {
      fetchHistory();
    }
  }, [selectedPort, selectedRange, fetchHistory]);

  /* Chart data */
  const chartData = React.useMemo(() => {
    return history.map((h) => ({
      t: h.timestamp,
      inKb: h.kb_s_in,
      outKb: h.kb_s_out,
    }));
  }, [history]);

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Historical Logs</h1>
        <div
          className={`connection-badge ${
            connected
              ? 'connection-badge--connected'
              : 'connection-badge--disconnected'
          }`}
        >
          <span className="connection-dot" />
          {connected ? 'Live' : 'Disconnected'}
        </div>
      </div>

      {/* Controls */}
      <div className="history-controls">
        <div className="history-controls__group">
          <label className="history-controls__label">Port</label>
          <select
            className="history-controls__select"
            value={selectedPort ?? ''}
            onChange={(e) =>
              setSelectedPort(e.target.value ? Number(e.target.value) : null)
            }
            id="history-port-select"
          >
            <option value="">Select a port…</option>
            {availablePorts.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
        </div>

        <div className="history-controls__group">
          <label className="history-controls__label">Time Range</label>
          <div className="btn-group" id="history-range-group">
            {TIME_RANGES.map((r) => (
              <button
                key={r.hours}
                className={`btn btn--sm ${
                  selectedRange === r.hours ? 'btn--active' : 'btn--ghost'
                }`}
                onClick={() => setSelectedRange(r.hours)}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>

        <button
          className="btn btn--sm btn--primary"
          onClick={fetchHistory}
          disabled={selectedPort == null || loading}
        >
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </div>

      {fetchError && (
        <div className="error-banner">{fetchError}</div>
      )}

      {/* Chart */}
      {selectedPort != null && chartData.length >= 2 && (
        <section className="traffic-chart-card" id="history-chart">
          <div className="traffic-chart-card__header">
            <span className="traffic-chart-card__title">
              Port {selectedPort} — Last {selectedRange}h
            </span>
            <span className="traffic-chart-card__legend">
              <span className="legend-dot legend-dot--blue" /> In &nbsp;
              <span className="legend-dot legend-dot--orange" /> Out
            </span>
          </div>
          <div style={{ width: '100%', height: 220 }}>
            <ResponsiveContainer>
              <AreaChart
                data={chartData}
                margin={{ top: 4, right: 12, bottom: 0, left: 0 }}
              >
                <defs>
                  <linearGradient id="hGradIn" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent-blue)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="var(--accent-blue)" stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="hGradOut" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent-orange)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="var(--accent-orange)" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis
                  dataKey="t"
                  tickFormatter={(t: number) => {
                    const d = new Date(t * 1000);
                    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
                  }}
                  tick={{ fill: '#484f58', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: '#484f58', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: number) => `${v.toFixed(0)}`}
                  width={36}
                />
                <Tooltip
                  contentStyle={{
                    background: '#111620',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  labelFormatter={(t: number) => {
                    const d = new Date(t * 1000);
                    return d.toLocaleTimeString();
                  }}
                  formatter={(val: number, name: string) => [
                    `${val.toFixed(2)} KB/s`,
                    name === 'inKb' ? 'In' : 'Out',
                  ]}
                />
                <Area
                  type="monotone"
                  dataKey="inKb"
                  stroke="var(--accent-blue)"
                  strokeWidth={1.5}
                  fill="url(#hGradIn)"
                  isAnimationActive={false}
                />
                <Area
                  type="monotone"
                  dataKey="outKb"
                  stroke="var(--accent-orange)"
                  strokeWidth={1.5}
                  fill="url(#hGradOut)"
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Data Table */}
      {selectedPort != null && history.length > 0 && (
        <div className="history-table-card">
          <table className="history-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>App</th>
                <th>PID</th>
                <th>Proto</th>
                <th style={{ textAlign: 'right' }}>In (KB/s)</th>
                <th style={{ textAlign: 'right' }}>Out (KB/s)</th>
              </tr>
            </thead>
            <tbody>
              {history.slice(-50).reverse().map((h, i) => (
                <tr key={h.id ?? i}>
                  <td>{new Date(h.timestamp * 1000).toLocaleTimeString()}</td>
                  <td>{h.app_name}</td>
                  <td className="mono">{h.pid}</td>
                  <td>{h.protocol}</td>
                  <td className="mono" style={{ textAlign: 'right', color: 'var(--accent-blue)' }}>
                    {h.kb_s_in.toFixed(2)}
                  </td>
                  <td className="mono" style={{ textAlign: 'right', color: 'var(--accent-orange)' }}>
                    {h.kb_s_out.toFixed(2)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty State */}
      {selectedPort == null && (
        <div className="empty-state" style={{ padding: '80px 0' }}>
          <div className="empty-state__icon">📈</div>
          <div className="empty-state__text">
            Select a port to view its traffic history
          </div>
        </div>
      )}

      {selectedPort != null && !loading && history.length === 0 && !fetchError && (
        <div className="empty-state" style={{ padding: '60px 0' }}>
          <div className="empty-state__icon">📭</div>
          <div className="empty-state__text">
            No historical data for port {selectedPort}
          </div>
        </div>
      )}
    </>
  );
};

export default HistoricalLogsPage;
