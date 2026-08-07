import React from 'react';
import { Shield, Server, Activity, Database } from 'lucide-react';
import { Card } from './ui/Card';
import { useSocketContext } from '../hooks/SocketContext';

export const KPIRow: React.FC = () => {
  const { connected, portTable } = useSocketContext();
  
  // Calculate some dummy metrics based on active data
  const totalConnections = portTable.length;
  const highRisk = portTable.filter(p => p.risk_score > 70).length;
  const activeProcesses = new Set(portTable.map(p => p.pid)).size;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 'var(--space-md)', marginBottom: 'var(--space-lg)' }}>
      <Card style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ padding: '12px', borderRadius: '50%', background: 'var(--accent-blue-dim)', color: 'var(--accent-blue)' }}>
          <Server size={24} />
        </div>
        <div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>System Health</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)' }}>{connected ? 'Optimal' : 'Offline'}</div>
        </div>
      </Card>

      <Card style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ padding: '12px', borderRadius: '50%', background: 'var(--accent-red-dim)', color: 'var(--accent-red)' }}>
          <Shield size={24} />
        </div>
        <div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Threat Score</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: highRisk > 0 ? 'var(--accent-red)' : 'var(--text-primary)' }}>
            {highRisk} Critical
          </div>
        </div>
      </Card>

      <Card style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ padding: '12px', borderRadius: '50%', background: 'var(--accent-green-dim)', color: 'var(--accent-green)' }}>
          <Activity size={24} />
        </div>
        <div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Active Connections</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)' }}>{totalConnections}</div>
        </div>
      </Card>

      <Card style={{ padding: '16px', display: 'flex', alignItems: 'center', gap: '16px' }}>
        <div style={{ padding: '12px', borderRadius: '50%', background: 'var(--bg-active)', color: 'var(--text-secondary)' }}>
          <Database size={24} />
        </div>
        <div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, textTransform: 'uppercase' }}>Tracked Processes</div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--text-primary)' }}>{activeProcesses}</div>
        </div>
      </Card>
    </div>
  );
};
