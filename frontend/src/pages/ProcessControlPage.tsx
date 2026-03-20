/**
 * Sentinel — Process Control Page
 *
 * Shows active processes grouped by app name with traffic bars
 * and action buttons (suspend, resume, kill) with confirmation modals.
 */

import React, { useState, useMemo, useCallback } from 'react';
import { useSocketContext } from '../SocketContext';
import ConfirmModal from '../components/ConfirmModal';
import type { ControlAction } from '../types';

interface ProcessGroup {
  pid: number;
  app_name: string;
  ports: number[];
  totalIn: number;
  totalOut: number;
  protocol: string;
}

const PROTECTED_PIDS = new Set([0, 1, 4]);

const ProcessControlPage: React.FC = () => {
  const { portTable, connected } = useSocketContext();
  const [pendingAction, setPendingAction] = useState<{
    action: ControlAction;
    pid: number;
    app: string;
  } | null>(null);
  const [actionResult, setActionResult] = useState<string | null>(null);

  /* Group port entries by PID */
  const processGroups = useMemo((): ProcessGroup[] => {
    const map = new Map<number, ProcessGroup>();
    for (const entry of portTable) {
      if (entry.pid <= 0) continue;
      const existing = map.get(entry.pid);
      if (existing) {
        existing.ports.push(entry.port);
        existing.totalIn += entry.kb_s_in ?? 0;
        existing.totalOut += entry.kb_s_out ?? 0;
      } else {
        map.set(entry.pid, {
          pid: entry.pid,
          app_name: entry.app_name,
          ports: [entry.port],
          totalIn: entry.kb_s_in ?? 0,
          totalOut: entry.kb_s_out ?? 0,
          protocol: entry.protocol,
        });
      }
    }
    return Array.from(map.values()).sort(
      (a, b) => b.totalIn + b.totalOut - (a.totalIn + a.totalOut)
    );
  }, [portTable]);

  const maxTraffic = useMemo(() => {
    if (processGroups.length === 0) return 1;
    return Math.max(
      ...processGroups.map((g) => g.totalIn + g.totalOut),
      0.01
    );
  }, [processGroups]);

  const executeAction = useCallback(async () => {
    if (!pendingAction) return;
    const { action, pid } = pendingAction;
    try {
      const resp = await fetch(`/api/control/${action}/${pid}`, {
        method: 'POST',
      });
      const data = await resp.json().catch(() => ({}));
      const detail =
        typeof data?.detail === 'string'
          ? data.detail
          : `HTTP ${resp.status}`;

      if (!resp.ok) {
        setActionResult(`✗ ${action} on PID ${pid} failed: ${detail}`);
      } else if (data.success) {
        setActionResult(`✓ ${action} on PID ${pid} succeeded`);
      } else {
        setActionResult(`✗ ${action} on PID ${pid} failed: ${detail}`);
      }
    } catch (e) {
      setActionResult(`✗ Network error: ${String(e)}`);
    }
    setPendingAction(null);
    setTimeout(() => setActionResult(null), 4000);
  }, [pendingAction]);

  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Process Control</h1>
        <div
          className={`connection-badge ${
            connected
              ? 'connection-badge--connected'
              : 'connection-badge--disconnected'
          }`}
        >
          <span className="connection-dot" />
          {connected ? 'Live' : 'Disconnected'}
        </div>
      </div>

      {actionResult && (
        <div
          className={`toast ${
            actionResult.startsWith('✓') ? 'toast--success' : 'toast--error'
          }`}
        >
          {actionResult}
        </div>
      )}

      {processGroups.length === 0 ? (
        <div className="empty-state" style={{ padding: '80px 0' }}>
          <div className="empty-state__icon">⚙️</div>
          <div className="empty-state__text">
            No active processes detected
          </div>
        </div>
      ) : (
        <div className="process-list">
          {processGroups.map((proc) => {
            const total = proc.totalIn + proc.totalOut;
            const controlsDisabled = PROTECTED_PIDS.has(proc.pid);
            const disabledTitle = controlsDisabled
              ? 'Protected system PID cannot be controlled'
              : undefined;

            return (
              <div key={proc.pid} className="process-card">
                <div className="process-card__info">
                  <div className="process-card__name">{proc.app_name}</div>
                  <div className="process-card__meta">
                    PID {proc.pid} · {proc.ports.length} port
                    {proc.ports.length !== 1 ? 's' : ''} ·{' '}
                    {proc.ports.slice(0, 5).join(', ')}
                    {proc.ports.length > 5 ? ` +${proc.ports.length - 5}` : ''}
                  </div>
                </div>

                <div className="process-card__bar-container">
                  <div className="process-card__bar">
                    <div
                      className="process-card__bar-fill process-card__bar-fill--in"
                      style={{ width: `${(proc.totalIn / maxTraffic) * 100}%` }}
                    />
                    <div
                      className="process-card__bar-fill process-card__bar-fill--out"
                      style={{
                        width: `${(proc.totalOut / maxTraffic) * 100}%`,
                        left: `${(proc.totalIn / maxTraffic) * 100}%`,
                      }}
                    />
                  </div>
                  <span className="process-card__rate">
                    {formatCompact(total)}
                  </span>
                </div>

                <div className="process-card__actions">
                  <button
                    className="btn btn--sm btn--ghost"
                    disabled={controlsDisabled}
                    onClick={() =>
                      setPendingAction({
                        action: 'suspend',
                        pid: proc.pid,
                        app: proc.app_name,
                      })
                    }
                    title={disabledTitle ?? 'Suspend process'}
                  >
                    ⏸
                  </button>
                  <button
                    className="btn btn--sm btn--ghost"
                    disabled={controlsDisabled}
                    onClick={() =>
                      setPendingAction({
                        action: 'resume',
                        pid: proc.pid,
                        app: proc.app_name,
                      })
                    }
                    title={disabledTitle ?? 'Resume process'}
                  >
                    ▶
                  </button>
                  <button
                    className="btn btn--sm btn--danger"
                    disabled={controlsDisabled}
                    onClick={() =>
                      setPendingAction({
                        action: 'kill',
                        pid: proc.pid,
                        app: proc.app_name,
                      })
                    }
                    title={disabledTitle ?? 'Kill process'}
                  >
                    ✕
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <ConfirmModal
        open={!!pendingAction}
        title={`${capitalize(pendingAction?.action ?? '')} Process`}
        message={`Are you sure you want to ${pendingAction?.action} "${pendingAction?.app}" (PID ${pendingAction?.pid})?`}
        confirmLabel={capitalize(pendingAction?.action ?? 'Confirm')}
        variant={pendingAction?.action === 'kill' ? 'danger' : 'warning'}
        onConfirm={executeAction}
        onCancel={() => setPendingAction(null)}
      />
    </>
  );
};

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function formatCompact(kbs: number): string {
  if (kbs < 0.1) return '0 KB/s';
  if (kbs >= 1024) return `${(kbs / 1024).toFixed(1)} MB/s`;
  return `${kbs.toFixed(1)} KB/s`;
}

export default ProcessControlPage;
