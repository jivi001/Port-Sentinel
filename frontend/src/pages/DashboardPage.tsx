/**
 * Vigilant — Operational Dashboard
 * 
 * Re-imagined with a dynamic, drag-and-drop widget layout system.
 * Integrates real-time Socket.IO feeds with customizable widgets.
 */

import React, { useState, useMemo, useEffect } from 'react';
import { ReactGridLayout, WidthProvider } from 'react-grid-layout/legacy';
import { useSocketContext } from '../hooks/SocketContext';
import PortTable from '../components/PortTable';
import ControlPanel from '../components/ControlPanel';
import { RotateCcw } from 'lucide-react';

import {
  TrafficWidget,
  ThreatWidget,
  TopTalkersWidget,
  AuditLogWidget,
  SystemHealthWidget,
  ApprovalQueueWidget,
} from '../components/DashboardWidgets';

import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';

const ReactGridLayoutWithWidth = WidthProvider(ReactGridLayout);

const DEFAULT_LAYOUT = [
  { i: 'traffic', x: 0, y: 0, w: 8, h: 3, minH: 3 },
  { i: 'threats', x: 8, y: 0, w: 4, h: 3, minH: 3 },
  { i: 'health', x: 0, y: 3, w: 4, h: 3, minH: 3 },
  { i: 'toptalkers', x: 4, y: 3, w: 4, h: 3, minH: 3 },
  { i: 'audit', x: 8, y: 3, w: 4, h: 3, minH: 3 },
  { i: 'approvals', x: 0, y: 6, w: 4, h: 3, minH: 3 },
];

const DashboardPage: React.FC = () => {
  const { portTable, sparklineData, connected, error } = useSocketContext();
  const [filter, setFilter] = useState('');
  const [layout, setLayout] = useState<any[]>(DEFAULT_LAYOUT);

  // Load layout from localStorage
  useEffect(() => {
    const saved = localStorage.getItem('vigilant_dashboard_layout');
    if (saved) {
      try {
        setLayout(JSON.parse(saved));
      } catch (e) {
        console.error('Failed to parse saved layout, using default', e);
      }
    }
  }, []);

  const handleLayoutChange = (newLayout: readonly any[]) => {
    setLayout(newLayout as any[]);
    localStorage.setItem('vigilant_dashboard_layout', JSON.stringify(newLayout));
  };

  const handleResetLayout = () => {
    setLayout(DEFAULT_LAYOUT);
    localStorage.setItem('vigilant_dashboard_layout', JSON.stringify(DEFAULT_LAYOUT));
  };

  // Aggregate traffic points from socket cache
  const totalTrafficChart = useMemo(() => {
    const timeMap = new Map<number, { t: number; inKb: number; outKb: number }>();
    sparklineData.forEach((points) => {
      for (const p of points) {
        const sec = Math.floor(p.t);
        const existing = timeMap.get(sec);
        if (existing) {
          existing.inKb += p.kbIn;
          existing.outKb -= p.kbOut;
        } else {
          timeMap.set(sec, { t: sec, inKb: p.kbIn, outKb: -p.kbOut });
        }
      }
    });
    return Array.from(timeMap.values())
      .sort((a, b) => a.t - b.t)
      .slice(-60);
  }, [sparklineData, portTable]);

  return (
    <div className="page-container" style={{ overflowY: 'auto' }}>
      <header className="page-header" style={{ borderBottom: '1px solid var(--border-dim)', paddingBottom: 'var(--space-md)' }}>
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-blue)', boxShadow: '0 0 10px var(--accent-blue)' }}></span>
            Operational Dashboard
          </h1>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
            Real-time network threat intelligence and traffic analysis.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
          <button 
            className="btn btn--sm" 
            onClick={handleResetLayout}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.7rem' }}
          >
            <RotateCcw size={12} />
            RESET WIDGETS
          </button>
          
          <div className={`connection-badge ${connected ? 'connection-badge--connected' : ''}`}>
            <span className="connection-dot" />
            {connected ? 'REAL_TIME_LINK_ACTIVE' : 'OFFLINE'}
          </div>
        </div>
      </header>

      {error && <div className="error-banner">⚠ SYSTEM_FAULT: {error}</div>}

      {/* Dynamic Customizable Widget Grid */}
      <div style={{ margin: '0 -10px' }}>
        <ReactGridLayoutWithWidth
          className="layout"
          layout={layout}
          cols={12}
          rowHeight={80}
          onLayoutChange={handleLayoutChange}
          draggableHandle=".widget-card__header"
          isResizable={true}
          isDraggable={true}
        >
          <div key="traffic">
            <TrafficWidget chartData={totalTrafficChart} />
          </div>
          <div key="threats">
            <ThreatWidget portTable={portTable} />
          </div>
          <div key="health">
            <SystemHealthWidget />
          </div>
          <div key="toptalkers">
            <TopTalkersWidget />
          </div>
          <div key="audit">
            <AuditLogWidget />
          </div>
          <div key="approvals">
            <ApprovalQueueWidget />
          </div>
        </ReactGridLayoutWithWidth>
      </div>

      {/* Main Port Table Section */}
      <section className="sentinel-section" style={{ marginTop: 'var(--space-lg)' }}>
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

export default DashboardPage;
