/**
 * Vigilant — Professional Settings & Configuration Page
 */

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { apiService } from '../services/apiService';
import ConfirmModal from '../components/ConfirmModal';
import { useTheme } from '../hooks/ThemeContext';
import { Settings, ShieldAlert, Monitor, HardDrive } from 'lucide-react';

const SettingsPage: React.FC = () => {
  const { theme, toggleTheme } = useTheme();
  
  // States
  const [blockedPorts, setBlockedPorts] = useState<any[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [toastColor, setToastColor] = useState<string>('var(--accent-green)');
  const [unblockPort, setUnblockPort] = useState<number | null>(null);
  
  // Console Preferences states
  const [refreshInterval, setRefreshInterval] = useState<string>('5');
  const [alertThreshold, setAlertThreshold] = useState<string>('7');

  const toastTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (toastTimeoutRef.current) clearTimeout(toastTimeoutRef.current);
    };
  }, []);

  const showToast = (msg: string, color: string = 'var(--accent-green)') => {
    setToastColor(color);
    setToast(msg);
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

  // Fetch preferences
  const fetchPrefs = useCallback(async () => {
    try {
      const prefs = await apiService.getPreferences();
      if (prefs.refresh_interval) setRefreshInterval(prefs.refresh_interval);
      if (prefs.alert_threshold) setAlertThreshold(prefs.alert_threshold);
    } catch (e) {
      console.warn('Could not load console preferences, using default');
    }
  }, []);

  useEffect(() => {
    fetchBlocked();
    fetchHealth();
    fetchPrefs();
    const inv = setInterval(fetchHealth, 5000);
    return () => clearInterval(inv);
  }, [fetchBlocked, fetchHealth, fetchPrefs]);

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

  const handlePreferenceChange = async (key: string, value: string) => {
    if (key === 'refresh_interval') setRefreshInterval(value);
    if (key === 'alert_threshold') setAlertThreshold(value);
    
    try {
      await apiService.setPreferences({ [key]: value });
      showToast(`✓ PREFERENCE ${key.toUpperCase()} SYNCED`);
    } catch (e) {
      console.error(e);
      showToast('FAILED TO SYNC PREFERENCE', 'var(--accent-red)');
    }
  };

  return (
    <div className="page-container">
      <header className="page-header">
        <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
          <Settings style={{ color: 'var(--accent-blue)' }} size={24} />
          Console Configuration
        </h1>
        {toast && <div className="connection-badge" style={{ color: toastColor }}>{toast}</div>}
      </header>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* System Health */}
        <section className="sentinel-section">
          <div className="sentinel-section__header">
            <h2 className="sentinel-section__title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <HardDrive size={14} />
              Operational Health
            </h2>
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
            <h2 className="sentinel-section__title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ShieldAlert size={14} />
              Firewall Policy (Hard Blocks)
            </h2>
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

        {/* Console Preferences */}
        <section className="sentinel-section" style={{ gridColumn: 'span 2' }}>
          <div className="sentinel-section__header">
            <h2 className="sentinel-section__title" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Monitor size={14} />
              User Configuration & Preferences
            </h2>
          </div>
          <div style={{ padding: '24px', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '24px' }}>
            <div className="kpi">
              <span className="kpi__label">Interface Theme</span>
              <select 
                value={theme} 
                onChange={toggleTheme}
                style={{ marginTop: '8px', padding: '6px', width: '100%' }}
              >
                <option value="dark">Dark Mode (Default)</option>
                <option value="light">Light Mode</option>
              </select>
            </div>
            
            <div className="kpi">
              <span className="kpi__label">UI Refresh Speed</span>
              <select 
                value={refreshInterval}
                onChange={(e) => handlePreferenceChange('refresh_interval', e.target.value)}
                style={{ marginTop: '8px', padding: '6px', width: '100%' }}
              >
                <option value="1">High Priority (1s)</option>
                <option value="5">Normal (5s)</option>
                <option value="10">Aggregated (10s)</option>
                <option value="30">Conservative (30s)</option>
              </select>
            </div>

            <div className="kpi">
              <span className="kpi__label">Alert Severity Filter</span>
              <select 
                value={alertThreshold}
                onChange={(e) => handlePreferenceChange('alert_threshold', e.target.value)}
                style={{ marginTop: '8px', padding: '6px', width: '100%' }}
              >
                <option value="5">Medium Severity (&gt;=5)</option>
                <option value="7">High Severity (&gt;=7)</option>
                <option value="8">Critical Severity (&gt;=8)</option>
                <option value="10">Emergency Only (10)</option>
              </select>
            </div>
          </div>
        </section>
      </div>

      <ConfirmModal 
        open={!!unblockPort} 
        title="Remove Firewall Rule?"
        message={`Restore connectivity to Port ${unblockPort}? This will remove the Vigilant firewall entry.`}
        onConfirm={handleUnblock}
        onCancel={() => setUnblockPort(null)}
      />
    </div>
  );
};

export default SettingsPage;
