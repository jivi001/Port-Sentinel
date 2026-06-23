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
    <div className="page-container h-full w-full flex flex-col">
      <header className="page-header flex justify-between items-center mb-4 shrink-0">
        <h1 className="page-title text-3xl font-bold text-text-main tracking-tight">Process Management</h1>
        <div className="flex items-center gap-3">
          {toast && (
            <div className="connection-badge flex items-center px-4 py-2 bg-surface rounded-full border border-border-main font-bold" style={{ color: toast.color }}>
              {toast.message}
            </div>
          )}
          <div className="connection-badge flex items-center px-4 py-2 bg-surface rounded-full border border-border-main text-primary font-bold">
            {processes.length} ACTIVE_PROCESSES
          </div>
        </div>
      </header>

      <div className="bg-surface border border-border-main rounded-xl shadow-lg flex flex-col overflow-hidden flex-1 min-h-0">
        <div className="p-4 bg-secondary/50 border-b border-border-main flex justify-between items-center">
          <h2 className="text-xs font-bold text-text-muted uppercase tracking-widest">Network-Active Processes</h2>
        </div>
        
        <div className="flex-1 flex flex-col min-h-0">
          <div className="flex items-center p-4 bg-secondary border-b border-border-main text-xs font-bold text-text-muted uppercase tracking-widest gap-4">
            <div className="w-20">PID</div>
            <div className="flex-[1.5] min-w-0">APPLICATION_NAME</div>
            <div className="w-36">ACTIVE_PORTS</div>
            <div className="w-36 text-right">INBOUND</div>
            <div className="w-36 text-right">OUTBOUND</div>
            <div className="w-36 text-right">ACTION</div>
          </div>
          
          <div className="flex-1 overflow-y-auto">
            {processes.map((proc) => (
              <div key={proc.pid} className="flex items-center p-4 border-b border-border-main hover:bg-hover transition-colors gap-4">
                <div className="w-20 font-mono text-text-muted font-semibold">{proc.pid}</div>
                <div className="flex-[1.5] min-w-0 font-bold text-text-main truncate">{proc.app_name}</div>
                <div className="w-36 font-mono text-primary font-semibold truncate">{Array.from(proc.ports).join(', ')}</div>
                <div className="w-36 text-right font-mono text-primary font-semibold">{proc.kb_s_in.toFixed(1)} KB/s</div>
                <div className="w-36 text-right font-mono text-warning font-semibold">{proc.kb_s_out.toFixed(1)} KB/s</div>
                <div className="w-36 text-right">
                  <button 
                    className="px-4 py-2 rounded-md font-bold text-xs bg-transparent text-danger hover:bg-danger/10 hover:text-text-main transition-colors border border-transparent hover:border-danger/30"
                    onClick={() => setTargetPid({ pid: proc.pid, appName: proc.app_name })}
                  >
                    SUSPEND
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

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
