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
      <span style={{ color: 'var(--accent-blue)' }}>{icon}</span>
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
    <WidgetHeader title="REAL-TIME THROUGHPUT (KB/S)" icon={<Activity size={16} />} />
    <div className="widget-card__body" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ flex: 1, minHeight: 0 }}>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="widgetIn" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent-blue)" stopOpacity={0.4} />
                <stop offset="100%" stopColor="var(--accent-blue)" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="widgetOut" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--accent-orange)" stopOpacity={0} />
                <stop offset="100%" stopColor="var(--accent-orange)" stopOpacity={0.3} />
              </linearGradient>
            </defs>
            <Area type="monotone" dataKey="inKb" stroke="var(--accent-blue)" fill="url(#widgetIn)" strokeWidth={3} isAnimationActive={false} />
            <Area type="monotone" dataKey="outKb" stroke="var(--accent-orange)" fill="url(#widgetOut)" strokeWidth={2} isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginTop: '12px', fontWeight: 800 }}>
        <span style={{ color: 'var(--accent-blue)', display: 'flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-blue)', boxShadow: '0 0 8px var(--accent-blue)' }}></span>
          INBOUND
        </span>
        <span style={{ color: 'var(--accent-orange)', display: 'flex', alignItems: 'center', gap: '4px' }}>
          OUTBOUND
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-orange)', boxShadow: '0 0 8px var(--accent-orange)' }}></span>
        </span>
      </div>
    </div>
  </div>
);

// 2. Threat Summary Widget
export const ThreatWidget: React.FC<{ portTable: any[] }> = ({ portTable }) => {
  const highRisk = portTable.filter(p => p.risk_score >= 7);
  const isDanger = highRisk.length > 0;
  
  return (
    <div className={`widget-card ${isDanger ? 'pulse-glow-red' : ''}`} style={{ borderColor: isDanger ? 'var(--accent-red)' : 'var(--card-border)' }}>
      <WidgetHeader title="SECURITY INTEL SUMMARY" icon={<Shield size={16} />} />
      <div className="widget-card__body" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', height: '100%', gap: '12px' }}>
        <span style={{ 
          fontSize: '3rem', 
          fontWeight: 900, 
          color: isDanger ? 'var(--accent-red)' : 'var(--accent-green)',
          textShadow: isDanger ? '0 0 20px var(--accent-red-glow)' : '0 0 20px var(--accent-green-glow)'
        }}>
          {highRisk.length}
        </span>
        <span style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '0.1em' }}>
          {isDanger ? 'ACTIVE HIGH-RISK THREATS' : 'SYSTEM FULLY SECURED'}
        </span>
        <div style={{ width: '40px', height: '4px', background: isDanger ? 'var(--accent-red)' : 'var(--accent-green)', borderRadius: '2px', boxShadow: `0 0 8px ${isDanger ? 'var(--accent-red)' : 'var(--accent-green)'}` }}></div>
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

  const maxKb = data.length > 0 ? Math.max(...data.map(d => d.total_kb ?? 0)) : 1;

  return (
    <div className="widget-card">
      <WidgetHeader title="TOP BANDWIDTH CONSUMERS" icon={<ListCollapse size={16} />} />
      <div className="widget-card__body" style={{ padding: '8px 16px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {data.length === 0 ? (
          <div style={{ padding: '20px', fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center' }}>No traffic recorded</div>
        ) : (
          data.map((item, index) => {
            const kb = item.total_kb ?? 0;
            const pct = Math.max(2, (kb / maxKb) * 100);
            return (
              <div key={item.app_name} style={{ display: 'flex', flexDirection: 'column', padding: '4px 0' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: '4px' }}>
                  <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{index + 1}. {item.app_name}</span>
                  <span className="mono" style={{ fontWeight: 800, color: 'var(--accent-blue)' }}>{(kb / 1024).toFixed(2)} MB</span>
                </div>
                <div className="progress-bar-container">
                  <div className="progress-bar-fill" style={{ width: `${pct}%` }}></div>
                </div>
              </div>
            );
          })
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
      <WidgetHeader title="RECENT SYSTEM AUDIT LOGS" icon={<AlertTriangle size={16} />} />
      <div className="widget-card__body" style={{ padding: '12px 16px', overflowY: 'auto' }}>
        {logs.length === 0 ? (
          <div style={{ padding: '20px', fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center' }}>No audit events logged</div>
        ) : (
          logs.map((log) => {
            const isCrit = log.severity === 'critical';
            return (
              <div key={log.id} style={{ fontSize: '0.75rem', padding: '8px 0', borderBottom: '1px solid var(--border-dim)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', alignItems: 'center' }}>
                  <span className={`badge ${isCrit ? 'badge--critical' : 'badge--info'}`}>
                    {log.event_type.toUpperCase()}
                  </span>
                  <span className="mono" style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>
                    {new Date(log.timestamp * 1000).toLocaleTimeString()}
                  </span>
                </div>
                <div style={{ color: 'var(--text-secondary)', lineHeight: '1.4' }}>{log.message}</div>
              </div>
            )
          })
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
      <WidgetHeader title="SYSTEM MONITORING HEALTH" icon={<HardDrive size={16} />} />
      <div className="widget-card__body" style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '0.8rem', padding: '20px 16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-dim)', paddingBottom: '8px', alignItems: 'center' }}>
          <span style={{ color: 'var(--text-muted)', fontWeight: 800 }}>SNIFFER STATUS:</span>
          <span className={`badge ${health?.sniffer_alive ? 'badge--success' : 'badge--critical'}`}>
            {health?.sniffer_alive ? 'ACTIVE' : 'FALLBACK'}
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-dim)', paddingBottom: '8px', alignItems: 'center' }}>
          <span style={{ color: 'var(--text-muted)', fontWeight: 800 }}>PORTS MONITORED:</span>
          <span className="mono" style={{ fontWeight: 800, color: 'var(--text-primary)', fontSize: '1rem' }}>{health?.ports_tracked ?? 0}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-dim)', paddingBottom: '8px', alignItems: 'center' }}>
          <span style={{ color: 'var(--text-muted)', fontWeight: 800 }}>UPTIME:</span>
          <span className="mono" style={{ fontWeight: 800, color: 'var(--text-primary)' }}>
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
      <WidgetHeader title="PENDING APPROVAL QUEUE" icon={<Users size={16} />} />
      <div className="widget-card__body" style={{ padding: '8px 16px', overflowY: 'auto' }}>
        {approvals.length === 0 ? (
          <div style={{ padding: '30px 10px', fontSize: '0.8rem', color: 'var(--text-muted)', textAlign: 'center', display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'center' }}>
            <Shield size={24} style={{ opacity: 0.3 }} />
            No actions requiring approval
          </div>
        ) : (
          approvals.map((req) => (
            <div key={req.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', padding: '10px 0', borderBottom: '1px solid var(--border-dim)' }}>
              <div>
                <div style={{ fontWeight: 800, color: 'var(--text-primary)' }}>PID {req.target_identifier}</div>
                <div style={{ color: 'var(--text-muted)', fontSize: '0.65rem', marginTop: '2px' }}>{req.reason}</div>
              </div>
              <button 
                className="btn btn--sm btn--primary" 
                style={{ padding: '4px 10px', fontSize: '0.7rem' }}
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
