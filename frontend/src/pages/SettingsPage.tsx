/**
 * Sentinel — Professional Settings Page
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { apiService } from '../services/apiService';
import ConfirmModal from '../components/ConfirmModal';

const SettingsPage: React.FC = () => {
  const [blockedPorts, setBlockedPorts] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [toast, setToast] = useState<{message: string, color: string} | null>(null);
  const [unblockPort, setUnblockPort] = useState<number | null>(null);

  const toastTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    };
  }, []);

  const showToast = (message: string, color: string = 'var(--accent-green)') => {
    setToast({ message, color });
    if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    toastTimeoutRef.current = window.setTimeout(() => setToast(null), 3000);
  };

  const fetchBlocked = useCallback(async () => {
    try {
      const data = await apiService.getBlockedPorts();
      setBlockedPorts(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchHealth = useCallback(async () => {
    try {
      const data = await apiService.getHealth();
      setHealth(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    fetchBlocked();
    fetchHealth();
    const inv = setInterval(fetchHealth, 5000);
    return () => clearInterval(inv);
  }, [fetchBlocked, fetchHealth]);

  const handleUnblock = async () => {
    if (unblockPort == null) return;
    const targetPort = unblockPort;
    try {
      const success = await apiService.unblockPort(targetPort);
      if (success) {
        showToast(`✓ PORT ${targetPort} UNBLOCKED`);
        fetchBlocked();
      } else {
        showToast(`RESTORE FAILED FOR PORT ${targetPort}`, 'var(--accent-red)');
      }
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Restore request failed';
      showToast(message.toUpperCase(), 'var(--accent-red)');
    }
    setUnblockPort(null);
  };

  return (
    <div className="page-container h-full w-full flex flex-col">
      <header className="page-header flex justify-between items-center mb-4 shrink-0">
        <h1 className="page-title text-3xl font-bold text-text-main tracking-tight">Console Configuration</h1>
        {toast && (
          <div className="connection-badge flex items-center px-4 py-2 bg-surface rounded-full border border-border-main font-bold" style={{ color: toast.color }}>
            {toast.message}
          </div>
        )}
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 flex-1 min-h-0">
        {/* System Health */}
        <section className="bg-surface border border-border-main rounded-xl shadow-lg flex flex-col overflow-hidden">
          <div className="p-4 bg-secondary/50 border-b border-border-main">
            <h2 className="text-xs font-bold text-text-muted uppercase tracking-widest">Operational Health</h2>
          </div>
          <div className="p-6 flex flex-col gap-5 flex-1 overflow-y-auto">
            <div className="flex justify-between items-center pb-4 border-b border-border-main">
              <span className="text-xs font-bold text-text-muted uppercase tracking-widest">System Kernel</span>
              <span className="font-mono text-sm font-bold text-accent">{health?.platform?.toUpperCase() || 'SEARCHING...'}</span>
            </div>
            <div className="flex justify-between items-center pb-4 border-b border-border-main">
              <span className="text-xs font-bold text-text-muted uppercase tracking-widest">Sniffer Status</span>
              <span className={`font-mono text-sm font-bold ${health?.sniffer_alive ? 'text-primary' : 'text-danger'}`}>
                {health?.sniffer_alive ? 'ACTIVE_SCANNING' : 'OFFLINE'}
              </span>
            </div>
            <div className="flex justify-between items-center pb-4 border-b border-border-main">
              <span className="text-xs font-bold text-text-muted uppercase tracking-widest">System Uptime</span>
              <span className="font-mono text-sm font-bold text-text-main">{health ? `${Math.floor(health.uptime_seconds / 60)}M` : '0M'}</span>
            </div>
          </div>
        </section>

        {/* Firewall Rules */}
        <section className="bg-surface border border-border-main rounded-xl shadow-lg flex flex-col overflow-hidden">
          <div className="p-4 bg-secondary/50 border-b border-border-main">
            <h2 className="text-xs font-bold text-text-muted uppercase tracking-widest">Firewall Policy (Hard Blocks)</h2>
          </div>
          <div className="flex-1 flex flex-col min-h-0">
            <div className="flex items-center p-4 bg-secondary border-b border-border-main text-xs font-bold text-text-muted uppercase tracking-widest gap-4">
              <div className="w-24">PORT</div>
              <div className="flex-1">REASON</div>
              <div className="w-24 text-right">ACTION</div>
            </div>
            <div className="flex-1 overflow-y-auto">
              {blockedPorts.length === 0 ? (
                <div className="p-16 text-center text-text-muted text-sm font-bold tracking-wider">NO ACTIVE BLOCKS</div>
              ) : (
                blockedPorts.map(p => (
                  <div key={p.port} className="flex items-center p-4 border-b border-border-main hover:bg-hover transition-colors gap-4">
                    <div className="w-24 font-mono text-danger font-semibold">{p.port}</div>
                    <div className="flex-1 text-xs text-text-muted truncate">{p.reason || 'MANUAL_BLOCK'}</div>
                    <div className="w-24 text-right">
                      <button 
                        className="px-3 py-1.5 rounded-md text-xs font-bold bg-transparent text-primary hover:bg-primary/10 border border-transparent hover:border-primary/30 transition-colors"
                        onClick={() => setUnblockPort(p.port)}
                      >
                        RESTORE
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </section>
      </div>

      <ConfirmModal 
        open={!!unblockPort} 
        title="Remove Firewall Rule?"
        message={`Restore connectivity to Port ${unblockPort}? This will remove the Sentinel_ firewall entry.`}
        onConfirm={handleUnblock}
        onCancel={() => setUnblockPort(null)}
      />
    </div>
  );
};

export default SettingsPage;
