/**
 * Sentinel — Professional Optimized Dashboard
 */

import React, { useState, useMemo } from 'react';
import { useSocketContext } from '../hooks/SocketContext';
import PortTable from '../components/PortTable';
import ControlPanel from '../components/ControlPanel';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';

const DashboardPage: React.FC = () => {
  const { portTable, sparklineData, connected, error } = useSocketContext();
  const [filter, setFilter] = useState('');

  const stats = useMemo(() => {
    const totalIn = portTable.reduce((s, p) => s + (p.kb_s_in ?? 0), 0);
    const totalOut = portTable.reduce((s, p) => s + (p.kb_s_out ?? 0), 0);
    const highRiskCount = portTable.filter(p => p.risk_score >= 7).length;
    return { totalIn, totalOut, highRiskCount };
  }, [portTable]);

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
    <div className="page-container">
      <header className="page-header">
        <h1 className="page-title">Operational Dashboard</h1>
        <div className={`connection-badge ${connected ? 'connection-badge--connected' : ''}`}>
          <span className="connection-dot" />
          {connected ? 'REAL_TIME_LINK_ACTIVE' : 'OFFLINE'}
        </div>
      </header>

      {error && <div className="error-banner">⚠ SYSTEM_FAULT: {error}</div>}

      {/* Primary KPI Metrics */}
      <div className="dashboard-summary">
        <div className="dashboard-mini-stats">
          <div className="kpi">
            <span className="kpi__label">TOTAL_THROUGHPUT</span>
            <span className="kpi__value">{formatRate(stats.totalIn + stats.totalOut)}</span>
          </div>
          <div className="kpi">
            <span className="kpi__label">ACTIVE_NODES</span>
            <span className="kpi__value">{portTable.length}</span>
          </div>
          <div className="kpi">
            <span className="kpi__label">SECURITY_STATE</span>
            <span className="kpi__value" style={{ color: stats.highRiskCount > 0 ? 'var(--accent-red)' : 'var(--accent-green)' }}>
              {stats.highRiskCount > 0 ? 'RISK_DETECTED' : 'SECURE'}
            </span>
          </div>
        </div>

        {/* Real-time Integrated Chart */}
        <div className="dashboard-compact-chart">
          <ResponsiveContainer width="100%" height={60}>
            <AreaChart data={totalTrafficChart}>
              <defs>
                <linearGradient id="miniIn" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--accent-blue)" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="var(--accent-blue)" stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area type="monotone" dataKey="inKb" stroke="var(--accent-blue)" fill="url(#miniIn)" strokeWidth={1.5} isAnimationActive={false} />
              <Area type="monotone" dataKey="outKb" stroke="var(--accent-orange)" fill="transparent" strokeWidth={1.5} isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Main Port Table Section */}
      <section className="sentinel-section" style={{ flex: 1, minHeight: 0 }}>
        <div className="sentinel-section__header">
          <h2 className="sentinel-section__title">Global Traffic Control</h2>
          <ControlPanel filter={filter} onFilterChange={setFilter} />
        </div>
        
        <div className="port-table-container">
          <PortTable data={portTable} sparklineData={sparklineData} filter={filter} />
        </div>
      </section>
    </div>
  );
};

function formatRate(kbs: number): string {
  if (kbs < 0.1) return '0.0 KB/s';
  if (kbs >= 1024) return `${(kbs / 1024).toFixed(1)} MB/s`;
  return `${kbs.toFixed(1)} KB/s`;
}

export default DashboardPage;
