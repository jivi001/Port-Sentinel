/**
 * Sentinel — Dashboard Page
 *
 * Main dashboard extracted from the original App.tsx.
 * Stats bar, control panel, port table, and total traffic chart.
 */

import React, { useState, useMemo } from 'react';
import { useSocketContext } from '../SocketContext';
import PortTable from '../components/PortTable';
import ControlPanel from '../components/ControlPanel';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';

const DashboardPage: React.FC = () => {
  const { portTable, sparklineData, connected, error } = useSocketContext();
  const [filter, setFilter] = useState('');

  const stats = useMemo(() => {
    const totalIn = portTable.reduce((s, p) => s + (p.kb_s_in ?? 0), 0);
    const totalOut = portTable.reduce((s, p) => s + (p.kb_s_out ?? 0), 0);
    const tcpCount = portTable.filter((p) => p.protocol === 'TCP').length;
    const udpCount = portTable.filter((p) => p.protocol === 'UDP').length;
    return { totalIn, totalOut, tcpCount, udpCount };
  }, [portTable]);

  /* Aggregate sparkline data for the total traffic chart */
  const totalTrafficChart = useMemo(() => {
    const timeMap = new Map<number, { t: number; inKb: number; outKb: number }>();
    sparklineData.forEach((points) => {
      for (const p of points) {
        const sec = Math.floor(p.t);
        const existing = timeMap.get(sec);
        if (existing) {
          existing.inKb += p.kbIn;
          existing.outKb += p.kbOut;
        } else {
          timeMap.set(sec, { t: sec, inKb: p.kbIn, outKb: p.kbOut });
        }
      }
    });
    return Array.from(timeMap.values())
      .sort((a, b) => a.t - b.t)
      .slice(-60);
  }, [sparklineData]);

  return (
    <>
      {/* Connection + Error */}
      <div className="page-header">
        <h1 className="page-title">Dashboard</h1>
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

      {error && (
        <div className="error-banner" id="error-banner">
          ⚠ {error}
        </div>
      )}

      {/* Stats Bar */}
      <section className="stats-bar" id="stats-bar">
        <div className="stat-card">
          <div className="stat-card__label">Active Ports</div>
          <div className="stat-card__value stat-card__value--blue">
            {portTable.length}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Total In</div>
          <div className="stat-card__value stat-card__value--cyan">
            {formatRate(stats.totalIn)}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">Total Out</div>
          <div className="stat-card__value stat-card__value--orange">
            {formatRate(stats.totalOut)}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-card__label">TCP / UDP</div>
          <div className="stat-card__value stat-card__value--green">
            {stats.tcpCount} / {stats.udpCount}
          </div>
        </div>
      </section>

      {/* Total Traffic Chart */}
      {totalTrafficChart.length >= 2 && (
        <section className="traffic-chart-card" id="traffic-chart">
          <div className="traffic-chart-card__header">
            <span className="traffic-chart-card__title">Total Traffic (60s)</span>
            <span className="traffic-chart-card__legend">
              <span className="legend-dot legend-dot--blue" /> In &nbsp;
              <span className="legend-dot legend-dot--orange" /> Out
            </span>
          </div>
          <div style={{ width: '100%', height: 180 }}>
            <ResponsiveContainer>
              <AreaChart data={totalTrafficChart} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="gradIn" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent-blue)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="var(--accent-blue)" stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="gradOut" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--accent-orange)" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="var(--accent-orange)" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="t" hide />
                <YAxis
                  tick={{ fill: '#484f58', fontSize: 10 }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v: number) => (v >= 1024 ? `${(v / 1024).toFixed(0)}M` : `${v.toFixed(0)}`)}
                  width={36}
                />
                <Tooltip
                  contentStyle={{
                    background: '#111620',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                  labelFormatter={() => ''}
                  formatter={(val: number, name: string) => [
                    `${val.toFixed(1)} KB/s`,
                    name === 'inKb' ? 'In' : 'Out',
                  ]}
                />
                <Area
                  type="monotone"
                  dataKey="inKb"
                  stroke="var(--accent-blue)"
                  strokeWidth={1.5}
                  fill="url(#gradIn)"
                  isAnimationActive={false}
                />
                <Area
                  type="monotone"
                  dataKey="outKb"
                  stroke="var(--accent-orange)"
                  strokeWidth={1.5}
                  fill="url(#gradOut)"
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Control Panel */}
      <ControlPanel
        filter={filter}
        onFilterChange={setFilter}
        portCount={portTable.length}
      />

      {/* Port Table */}
      <PortTable data={portTable} sparklineData={sparklineData} filter={filter} />
    </>
  );
};

/** Format KB/s rate with unit suffix */
function formatRate(kbs: number): string {
  if (kbs < 0.1) return '0 KB/s';
  if (kbs >= 1024) return `${(kbs / 1024).toFixed(1)} MB/s`;
  return `${kbs.toFixed(1)} KB/s`;
}

export default DashboardPage;
