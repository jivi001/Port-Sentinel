/**
 * Vigilant — Modular Dashboard Widgets
 * 
 * Reusable card components for the drag-and-drop dashboard grid layout.
 * Integrates real-time socket data and poll-based API endpoints.
 */

import React, { useState, useEffect } from 'react';
import { AreaChart, Area, ResponsiveContainer } from 'recharts';
import { apiService } from '../services/apiService';
import { Shield, Activity, HardDrive, ListCollapse, Users, AlertTriangle } from 'lucide-react';

interface WidgetHeaderProps {
  title: string;
  icon: React.ReactNode;
  onRemove?: () => void;
}

export const WidgetHeader: React.FC<WidgetHeaderProps> = ({ title, icon, onRemove }) => (
  <div className="widget-card__header">
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <span style={{ color: 'var(--text-muted)' }}>{icon}</span>
      <span className="widget-card__title">{title}</span>
    </div>
    {onRemove && (
      <button 
        onClick={onRemove}
        style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.75rem' }}
        title="Remove Widget"
      >
        ✕
      </button>
    )}
  </div>
);

// 1. Traffic Throughput Widget
export const TrafficWidget: React.FC<{ chartData: any[] }> = ({ chartData }) => (
  <div className="widget-card">
    <WidgetHeader title="REAL-TIME THROUGHPUT (KB/S)" icon={<Activity size={14} />} />
    <div className="widget-card__body" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="widgetIn" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent-blue)" stopOpacity={0.2} />
                <stop offset="100%" stopColor="var(--accent-blue)" stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area type="monotone" dataKey="inKb" stroke="var(--accent-blue)" fill="url(#widgetIn)" strokeWidth={2} isAnimationActive={false} />
            <Area type="monotone" dataKey="outKb" stroke="var(--accent-orange)" fill="transparent" strokeWidth={2} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginTop: '8px', fontWeight: 800 }}>
        <span style={{ color: 'var(--accent-blue)' }}>↓ INBOUND</span>
        <span style={{ color: 'var(--accent-orange)' }}>↑ OUTBOUND</span>
      </div>
    </div>
  </div>
);

// 2. Threat Summary Widget
export const ThreatWidget: React.FC<{ portTable: any[] }> = ({ portTable }) => {
  const highRisk = portTable.filter(p => p.risk_score >= 7);
  return (
    <div className="widget-card">
      <WidgetHeader title="SECURITY INTEL SUMMARY" icon={<Shield size={14} />} />
      <div className="widget-card__body" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%', gap: '8px' }}>
        <span style={{ fontSize: '2.5rem', fontWeight: 900, color: highRisk.length > 0 ? 'var(--accent-red)' : 'var(--accent-green)' }}>
          {highRisk.length}
        </span>
        <span style={{ fontSize: '0.7rem', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
          {highRisk.length > 0 ? 'ACTIVE HIGH-RISK THREATS' : 'SYSTEM FULLY SECURED'}
        </span>
      </div>
    </div>
  );
};

// 3. Top Talkers Widget
export const TopTalkersWidget: React.FC = () => {
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    const fetchTalkers = async () => {
      try {
        const res = await apiService.getTopTalkers(24, 5);
        setData(res);
      } catch (e) {
        console.error(e);
      }
    };
    fetchTalkers();
    const interval = setInterval(fetchTalkers, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="widget-card">
      <WidgetHeader title="TOP BANDWIDTH CONSUMERS" icon={<ListCollapse size={14} />} />
      <div className="widget-card__body" style={{ padding: '8px' }}>
        {data.length === 0 ? (
          <div style={{ padding: '20px', fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center' }}>No traffic recorded</div>
        ) : (
          data.map((item, index) => (
            <div key={item.app_name} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', padding: '6px', borderBottom: '1px solid var(--border-dim)' }}>
              <span>{index + 1}. {item.app_name}</span>
              <span className="mono" style={{ fontWeight: 800 }}>{((item.total_kb ?? 0) / 1024).toFixed(2)} MB</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

// 4. Recent Audit Logs Widget
export const AuditLogWidget: React.FC = () => {
  const [logs, setLogs] = useState<any[]>([]);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const res = await apiService.getAuditLogs(5);
        setLogs(res);
      } catch (e) {
        console.error(e);
      }
    };
    fetchLogs();
    const interval = setInterval(fetchLogs, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="widget-card">
      <WidgetHeader title="RECENT SYSTEM AUDIT LOGS" icon={<AlertTriangle size={14} />} />
      <div className="widget-card__body" style={{ padding: '8px' }}>
        {logs.length === 0 ? (
          <div style={{ padding: '20px', fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center' }}>No audit events logged</div>
        ) : (
          logs.map((log) => (
            <div key={log.id} style={{ fontSize: '0.7rem', padding: '6px', borderBottom: '1px solid var(--border-dim)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px', fontWeight: 800 }}>
                <span style={{ color: log.severity === 'critical' ? 'var(--accent-red)' : 'var(--accent-blue)' }}>
                  {log.event_type.toUpperCase()}
                </span>
                <span className="mono" style={{ color: 'var(--text-muted)' }}>
                  {new Date(log.timestamp * 1000).toLocaleTimeString()}
                </span>
              </div>
              <div style={{ color: 'var(--text-secondary)' }}>{log.message}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

// 5. System Health Widget
export const SystemHealthWidget: React.FC = () => {
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await apiService.getHealth();
        setHealth(res);
      } catch (e) {
        console.error(e);
      }
    };
    fetchHealth();
    const interval = setInterval(fetchHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="widget-card">
      <WidgetHeader title="SYSTEM MONITORING HEALTH" icon={<HardDrive size={14} />} />
      <div className="widget-card__body" style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.75rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-dim)', paddingBottom: '4px' }}>
          <span style={{ color: 'var(--text-muted)', fontWeight: 800 }}>SNIFFER STATUS:</span>
          <span style={{ color: health?.sniffer_alive ? 'var(--accent-green)' : 'var(--accent-red)', fontWeight: 800 }}>
            {health?.sniffer_alive ? 'ACTIVE' : 'FALLBACK'}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-dim)', paddingBottom: '4px' }}>
          <span style={{ color: 'var(--text-muted)', fontWeight: 800 }}>PORTS MONITORED:</span>
          <span className="mono" style={{ fontWeight: 800 }}>{health?.ports_tracked ?? 0}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-dim)', paddingBottom: '4px' }}>
          <span style={{ color: 'var(--text-muted)', fontWeight: 800 }}>UPTIME:</span>
          <span className="mono" style={{ fontWeight: 800 }}>
            {health?.uptime_seconds ? `${Math.floor(health.uptime_seconds / 60)}m ${Math.floor(health.uptime_seconds % 60)}s` : 'Unknown'}
          </span>
        </div>
      </div>
    </div>
  );
};

// 6. Approval Queue Widget
export const ApprovalQueueWidget: React.FC = () => {
  const [approvals, setApprovals] = useState<any[]>([]);

  useEffect(() => {
    const fetchApprovals = async () => {
      try {
        const res = await apiService.getApprovals();
        setApprovals(res.filter((r: any) => r.status === 'pending'));
      } catch (e) {
        console.error(e);
      }
    };
    fetchApprovals();
    const interval = setInterval(fetchApprovals, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="widget-card">
      <WidgetHeader title="PENDING APPROVAL QUEUE" icon={<Users size={14} />} />
      <div className="widget-card__body" style={{ padding: '8px' }}>
        {approvals.length === 0 ? (
          <div style={{ padding: '20px', fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'center' }}>No actions requiring approval</div>
        ) : (
          approvals.map((req) => (
            <div key={req.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.7rem', padding: '6px', borderBottom: '1px solid var(--border-dim)' }}>
              <div>
                <div style={{ fontWeight: 800 }}>PID {req.target_identifier}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.6rem' }}>{req.reason}</div>
              </div>
              <button 
                className="btn btn--sm btn--primary" 
                style={{ padding: '2px 6px', fontSize: '0.65rem' }}
                onClick={() => apiService.resolveApproval(req.id, 'approved')}
              >
                APPROVE
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
