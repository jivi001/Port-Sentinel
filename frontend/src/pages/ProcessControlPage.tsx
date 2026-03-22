/**
 * Sentinel — Professional Process Control
 */

import React, { useState, useMemo } from 'react';
import { useSocketContext } from '../hooks/SocketContext';
import { apiService } from '../services/apiService';
import ConfirmModal from '../components/ConfirmModal';

const ProcessControlPage: React.FC = () => {
  const { portTable } = useSocketContext();
  const [killPid, setKillPid] = useState<number | null>(null);
  const [toast, setToast] = useState<{ message: string; color: string } | null>(null);

  const showToast = (message: string, color: string) => {
    setToast({ message, color });
    setTimeout(() => setToast(null), 3000);
  };

  const processes = useMemo(() => {
    const map = new Map<number, any>();
    portTable.forEach(p => {
      if (p.pid && p.pid > 0) {
        const existing = map.get(p.pid);
        if (existing) {
          existing.kb_s_in += p.kb_s_in;
          existing.kb_s_out += p.kb_s_out;
          existing.ports.add(p.port);
        } else {
          map.set(p.pid, { 
            pid: p.pid, 
            app_name: p.app_name, 
            kb_s_in: p.kb_s_in, 
            kb_s_out: p.kb_s_out, 
            ports: new Set([p.port]),
            risk: p.risk_score 
          });
        }
      }
    });
    return Array.from(map.values()).sort((a, b) => (b.kb_s_in + b.kb_s_out) - (a.kb_s_in + a.kb_s_out));
  }, [portTable]);

  const handleKill = async () => {
    if (!killPid) return;
    const targetPid = killPid;
    try {
      const success = await apiService.killProcess(targetPid);
      if (!success) {
        showToast(`TERMINATE FAILED FOR PID ${targetPid}`, 'var(--accent-red)');
      } else {
        showToast(`PID ${targetPid} TERMINATED`, 'var(--accent-green)');
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Terminate request failed';
      showToast(message.toUpperCase(), 'var(--accent-red)');
    }
    setKillPid(null);
  };

  return (
    <div className="page-container">
      <header className="page-header">
        <h1 className="page-title">Process Management</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {toast && (
            <div className="connection-badge" style={{ color: toast.color }}>
              {toast.message}
            </div>
          )}
          <div className="connection-badge">
            {processes.length} ACTIVE_PROCESSES
          </div>
        </div>
      </header>

      <section className="sentinel-section" style={{ flex: 1 }}>
        <div className="sentinel-section__header">
          <h2 className="sentinel-section__title">Network-Active Processes</h2>
        </div>
        
        <div className="data-table-container">
          <div className="data-table-header">
            <div className="col-sm">PID</div>
            <div className="col-lg">APPLICATION_NAME</div>
            <div className="col-md">ACTIVE_PORTS</div>
            <div className="col-md col-right">INBOUND</div>
            <div className="col-md col-right">OUTBOUND</div>
            <div className="col-md col-right">ACTION</div>
          </div>
          
          <div className="data-table-body">
            {processes.map((proc) => (
              <div key={proc.pid} className="data-row">
                <div className="col-sm mono text-muted">{proc.pid}</div>
                <div className="col-lg" style={{ fontWeight: 700, color: 'white' }}>{proc.app_name}</div>
                <div className="col-md mono text-blue">{Array.from(proc.ports).join(', ')}</div>
                <div className="col-md col-right mono text-blue">{proc.kb_s_in.toFixed(1)} KB/s</div>
                <div className="col-md col-right mono text-orange">{proc.kb_s_out.toFixed(1)} KB/s</div>
                <div className="col-md col-right">
                  <button className="btn" style={{ color: 'var(--accent-red)' }} onClick={() => setKillPid(proc.pid)}>TERMINATE</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <ConfirmModal 
        open={!!killPid} 
        title="Terminate Process?"
        message={`Warning: Killing PID ${killPid} will immediately stop its network activity and may cause data loss.`}
        onConfirm={handleKill}
        onCancel={() => setKillPid(null)}
      />
    </div>
  );
};

export default ProcessControlPage;
