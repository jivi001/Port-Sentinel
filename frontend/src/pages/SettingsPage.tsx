/**
 * Sentinel — Settings Page
 *
 * Blocked ports management, health status, and configuration.
 */

import React, { useState, useEffect, useCallback } from 'react';
import ConfirmModal from '../components/ConfirmModal';
import type { BlockedPort, HealthResponse } from '../types';

const SettingsPage: React.FC = () => {
  const [blockedPorts, setBlockedPorts] = useState<BlockedPort[]>([]);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [newPort, setNewPort] = useState('');
  const [newReason, setNewReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [unblockPort, setUnblockPort] = useState<number | null>(null);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  /* Fetch blocked ports */
  const fetchBlocked = useCallback(async () => {
    try {
      const resp = await fetch('/api/blocked');
      if (resp.ok) {
        const data = await resp.json();
        setBlockedPorts(Array.isArray(data) ? data : []);
      }
    } catch (e) {
      console.error('Failed to fetch blocked ports', e);
    }
  }, []);

  /* Fetch health */
  const fetchHealth = useCallback(async () => {
    try {
      const resp = await fetch('/api/health');
      if (resp.ok) {
        setHealth(await resp.json());
      }
    } catch (e) {
      console.error('Failed to fetch health', e);
    }
  }, []);

  useEffect(() => {
    fetchBlocked();
    fetchHealth();
    const interval = setInterval(fetchHealth, 10000);
    return () => clearInterval(interval);
  }, [fetchBlocked, fetchHealth]);

  /* Block a port */
  const handleBlock = async () => {
    const portNum = parseInt(newPort, 10);
    if (isNaN(portNum) || portNum < 1 || portNum > 65535) {
      setError('Enter a valid port (1–65535)');
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`/api/control/block/${portNum}`, {
        method: 'POST',
      });
      if (resp.ok) {
        showToast(`✓ Port ${portNum} blocked`);
        setNewPort('');
        setNewReason('');
        fetchBlocked();
      } else {
        setError('Failed to block port');
      }
    } catch (e) {
      setError(`Network error: ${String(e)}`);
    } finally {
      setLoading(false);
    }
  };

  /* Unblock a port */
  const handleUnblock = async () => {
    if (unblockPort == null) return;
    try {
      const resp = await fetch(`/api/control/unblock/${unblockPort}`, {
        method: 'POST',
      });
      if (resp.ok) {
        showToast(`✓ Port ${unblockPort} unblocked`);
        fetchBlocked();
      }
    } catch (e) {
      console.error(e);
    }
    setUnblockPort(null);
  };

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Settings</h1>
      </div>

      {toast && <div className="toast toast--success">{toast}</div>}

      {/* Health Status Section */}
      <section className="settings-section">
        <h2 className="settings-section__title">System Status</h2>
        {health ? (
          <div className="stats-bar" style={{ marginBottom: 0 }}>
            <div className="stat-card">
              <div className="stat-card__label">Platform</div>
              <div className="stat-card__value stat-card__value--blue">
                {health.platform}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card__label">Sniffer</div>
              <div
                className={`stat-card__value ${
                  health.sniffer_alive
                    ? 'stat-card__value--green'
                    : 'stat-card__value--orange'
                }`}
              >
                {health.sniffer_alive ? 'Active' : 'Down'}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card__label">Ports Tracked</div>
              <div className="stat-card__value stat-card__value--cyan">
                {health.ports_tracked}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-card__label">Uptime</div>
              <div className="stat-card__value stat-card__value--green">
                {formatUptime(health.uptime_seconds)}
              </div>
            </div>
          </div>
        ) : (
          <div className="empty-state" style={{ padding: '24px 0' }}>
            <div className="empty-state__text">Loading health data…</div>
          </div>
        )}
      </section>

      {/* Blocked Ports Section */}
      <section className="settings-section">
        <h2 className="settings-section__title">Blocked Ports</h2>

        {/* Add Port Form */}
        <div className="settings-form">
          <input
            className="control-panel__search"
            type="number"
            placeholder="Port number"
            value={newPort}
            onChange={(e) => setNewPort(e.target.value)}
            min={1}
            max={65535}
            style={{ width: 140 }}
            id="block-port-input"
          />
          <input
            className="control-panel__search"
            type="text"
            placeholder="Reason (optional)"
            value={newReason}
            onChange={(e) => setNewReason(e.target.value)}
            style={{ flex: 1 }}
          />
          <button
            className="btn btn--sm btn--danger"
            onClick={handleBlock}
            disabled={loading || !newPort}
          >
            {loading ? 'Blocking…' : 'Block Port'}
          </button>
        </div>

        {error && <div className="error-banner" style={{ marginTop: 8 }}>{error}</div>}

        {/* Blocked Ports List */}
        {blockedPorts.length === 0 ? (
          <div className="empty-state" style={{ padding: '32px 0' }}>
            <div className="empty-state__icon">🛡️</div>
            <div className="empty-state__text">No ports are currently blocked</div>
          </div>
        ) : (
          <div className="blocked-list">
            {blockedPorts.map((bp) => (
              <div key={bp.port} className="blocked-item">
                <div className="blocked-item__port">{bp.port}</div>
                <div className="blocked-item__info">
                  <span className="blocked-item__type">{bp.block_type}</span>
                  {bp.reason && (
                    <span className="blocked-item__reason">{bp.reason}</span>
                  )}
                </div>
                <button
                  className="btn btn--sm btn--ghost"
                  onClick={() => setUnblockPort(bp.port)}
                  title="Unblock this port"
                >
                  ✕ Unblock
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      <ConfirmModal
        open={unblockPort != null}
        title="Unblock Port"
        message={`Remove port ${unblockPort} from the blocked list?`}
        confirmLabel="Unblock"
        variant="warning"
        onConfirm={handleUnblock}
        onCancel={() => setUnblockPort(null)}
      />
    </>
  );
};

function formatUptime(secs: number): string {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export default SettingsPage;
