/**
 * Sentinel — Professional Settings Page
 */

import React, { useState, useEffect, useCallback } from 'react';
import { apiService } from '../services/apiService';
import ConfirmModal from '../components/ConfirmModal';

const SettingsPage: React.FC = () => {
  const [blockedPorts, setBlockedPorts] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [toastColor, setToastColor] = useState<string>('var(--accent-green)');
  const [unblockPort, setUnblockPort] = useState<number | null>(null);

  const showToast = (msg: string, color: string = 'var(--accent-green)') => {
    setToastColor(color);
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
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
    <div className="page-container">
      <header className="page-header">
        <h1 className="page-title">Console Configuration</h1>
        {toast && <div className="connection-badge" style={{ color: toastColor }}>{toast}</div>}
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* System Health */}
        <section className="sentinel-section">
          <div className="sentinel-section__header">
            <h2 className="sentinel-section__title">Operational Health</h2>
          </div>
          <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div className="kpi">
              <span className="kpi__label">System Kernel</span>
              <span className="kpi__value" style={{ color: 'var(--accent-green)' }}>{health?.platform?.toUpperCase() || 'SEARCHING...'}</span>
            </div>
            <div className="kpi">
              <span className="kpi__label">Sniffer Status</span>
              <span className="kpi__value" style={{ color: health?.sniffer_alive ? 'var(--accent-blue)' : 'var(--accent-red)' }}>
                {health?.sniffer_alive ? 'ACTIVE_SCANNING' : 'OFFLINE'}
              </span>
            </div>
            <div className="kpi">
              <span className="kpi__label">System Uptime</span>
              <span className="kpi__value">{health ? `${Math.floor(health.uptime_seconds / 60)}M` : '0M'}</span>
            </div>
          </div>
        </section>

        {/* Firewall Rules */}
        <section className="sentinel-section">
          <div className="sentinel-section__header">
            <h2 className="sentinel-section__title">Firewall Policy (Hard Blocks)</h2>
          </div>
          <div className="data-table-container">
            <div className="data-table-header">
              <div className="col-sm">PORT</div>
              <div className="col-flex">REASON</div>
              <div className="col-md col-right">ACTION</div>
            </div>
            <div className="data-table-body" style={{ maxHeight: '300px' }}>
              {blockedPorts.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.75rem' }}>NO ACTIVE BLOCKS</div>
              ) : (
                blockedPorts.map(p => (
                  <div key={p.port} className="data-row">
                    <div className="col-sm mono text-red">{p.port}</div>
                    <div className="col-flex text-muted" style={{ fontSize: '0.7rem' }}>{p.reason || 'MANUAL_BLOCK'}</div>
                    <div className="col-md col-right">
                      <button className="btn" style={{ color: 'var(--accent-blue)' }} onClick={() => setUnblockPort(p.port)}>RESTORE</button>
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
