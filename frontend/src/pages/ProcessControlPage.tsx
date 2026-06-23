/**
 * Sentinel — Professional Process Control
 */

import React, { useState, useMemo, useRef, useEffect } from 'react';
import { useSocketContext } from '../hooks/SocketContext';
import { apiService } from '../services/apiService';
import ConfirmModal from '../components/ConfirmModal';

const ProcessControlPage: React.FC = () => {
  const { portTable } = useSocketContext();
  const [targetPid, setTargetPid] = useState<{ pid: number, appName: string } | null>(null);
  const [toast, setToast] = useState<{ message: string; color: string } | null>(null);
  const toastTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    };
  }, []);

  const showToast = (message: string, color: string) => {
    setToast({ message, color });
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    toastTimeoutRef.current = window.setTimeout(() => setToast(null), 3000);
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

  const handleRequestApproval = async () => {
    if (!targetPid) return;
    try {
      await apiService.requestApproval(targetPid.pid, targetPid.appName, `User requested suspension for PID ${targetPid.pid}`);
      showToast(`APPROVAL REQUESTED FOR PID ${targetPid.pid}`, 'var(--accent-blue)');
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Request failed';
      showToast(message.toUpperCase(), 'var(--accent-red)');
    }
    setTargetPid(null);
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
                <div className="col-sm mono" style={{ color: 'var(--text-muted)' }}>{proc.pid}</div>
                <div className="col-lg" style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{proc.app_name}</div>
                <div className="col-md mono" style={{ color: 'var(--accent-blue)' }}>{Array.from(proc.ports).join(', ')}</div>
                <div className="col-md col-right mono" style={{ color: 'var(--accent-blue)' }}>{proc.kb_s_in.toFixed(1)} KB/s</div>
                <div className="col-md col-right mono" style={{ color: 'var(--accent-orange)' }}>{proc.kb_s_out.toFixed(1)} KB/s</div>
                <div className="col-md col-right">
                  <button 
                    className="btn" 
                    style={{ color: 'var(--accent-red)' }} 
                    onClick={() => setTargetPid({ pid: proc.pid, appName: proc.app_name })}
                  >
                    SUSPEND
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <ConfirmModal 
        open={!!targetPid} 
        title="Request Process Suspension?"
        message={`Warning: Suspending PID ${targetPid?.pid} requires Analyst approval. It will not be suspended immediately.`}
        onConfirm={handleRequestApproval}
        onCancel={() => setTargetPid(null)}
      />
    </div>
  );
};

export default ProcessControlPage;
