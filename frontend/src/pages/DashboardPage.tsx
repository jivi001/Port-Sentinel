/**
 * Sentinel — Professional Optimized Dashboard
 */

import React, { useState, useMemo } from 'react';
import { useSocketContext } from '../hooks/SocketContext';
import PortTable from '../components/PortTable';
import ControlPanel from '../components/ControlPanel';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import { Responsive as ResponsiveGridLayout } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

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

  // Define layout for grid
  const layout = [
    { i: 'kpi', x: 0, y: 0, w: 12, h: 2, static: true },
    { i: 'table', x: 0, y: 2, w: 12, h: 8 },
  ];

  return (
    <div className="page-container h-full w-full overflow-y-auto">
      <header className="page-header flex justify-between items-center mb-4">
        <h1 className="page-title text-3xl font-bold text-text-main tracking-tight">Operational Dashboard</h1>
        <div className={`connection-badge ${connected ? 'text-accent' : 'text-danger'} flex items-center gap-2 px-4 py-2 bg-surface rounded-full border border-border-main`}>
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-accent animate-pulse' : 'bg-danger'}`} />
          {connected ? 'REAL_TIME_LINK_ACTIVE' : 'OFFLINE'}
        </div>
      </header>

      {error && <div className="bg-danger text-white p-3 rounded-md mb-4 shadow-lg">⚠ SYSTEM_FAULT: {error}</div>}

      <ResponsiveGridLayout 
        className="layout" 
        layouts={{ lg: layout }} 
        breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
        cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }} 
        rowHeight={60} 
        width={1500}
      >
        {/* Primary KPI Metrics */}
        <div key="kpi" className="bg-surface border border-border-main rounded-xl p-6 flex justify-between items-center shadow-lg cursor-move">
          <div className="flex gap-16">
            <div className="flex flex-col">
              <span className="text-xs uppercase font-bold text-text-muted tracking-wider">TOTAL_THROUGHPUT</span>
              <span className="text-2xl font-mono font-bold text-text-main mt-1">{formatRate(stats.totalIn + stats.totalOut)}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-xs uppercase font-bold text-text-muted tracking-wider">ACTIVE_NODES</span>
              <span className="text-2xl font-mono font-bold text-text-main mt-1">{portTable.length}</span>
            </div>
            <div className="flex flex-col">
              <span className="text-xs uppercase font-bold text-text-muted tracking-wider">SECURITY_STATE</span>
              <span className={`text-2xl font-mono font-bold mt-1 ${stats.highRiskCount > 0 ? 'text-danger' : 'text-accent'}`}>
                {stats.highRiskCount > 0 ? 'RISK_DETECTED' : 'SECURE'}
              </span>
            </div>
          </div>

          {/* Real-time Integrated Chart */}
          <div className="flex-1 max-w-lg h-16 opacity-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={totalTrafficChart}>
                <defs>
                  <linearGradient id="miniIn" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.2} />
                    <stop offset="100%" stopColor="#3B82F6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area type="monotone" dataKey="inKb" stroke="#3B82F6" fill="url(#miniIn)" strokeWidth={1.5} isAnimationActive={false} />
                <Area type="monotone" dataKey="outKb" stroke="#F59E0B" fill="transparent" strokeWidth={1.5} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Main Port Table Section */}
        <div key="table" className="bg-surface border border-border-main rounded-xl shadow-lg flex flex-col overflow-hidden">
          <div className="p-4 bg-secondary/50 border-b border-border-main flex justify-between items-center cursor-move">
            <h2 className="text-xs font-bold text-text-muted uppercase tracking-widest">Global Traffic Control</h2>
            <ControlPanel filter={filter} onFilterChange={setFilter} />
          </div>
          <div className="flex-1 overflow-hidden flex flex-col">
            <PortTable data={portTable} sparklineData={sparklineData} filter={filter} />
          </div>
        </div>
      </ResponsiveGridLayout>
    </div>
  );
};

function formatRate(kbs: number): string {
  if (kbs < 0.1) return '0.0 KB/s';
  if (kbs >= 1024) return `${(kbs / 1024).toFixed(1)} MB/s`;
  return `${kbs.toFixed(1)} KB/s`;
}

export default DashboardPage;
