/**
 * Sentinel — Professional Network Intelligence
 * 
 * Clean, logical Network Topology visualization.
 * Hardcoded to Cyber Midnight design language.
 */

import React, { useMemo } from 'react';
import { useSocketContext } from '../hooks/SocketContext';

const NetworkMapPage: React.FC = () => {
  const { portTable, connected } = useSocketContext();

  const activeConnections = useMemo(() => {
    return portTable.filter(p => p.remote_ip !== "0.0.0.0");
  }, [portTable]);

  return (
    <div className="page-container">
      <header className="page-header">
        <h1 className="page-title">Network Intelligence</h1>
        <div className="connection-badge connection-badge--connected">
          <span className="connection-dot" />
          {connected ? 'TOPOLOGY_SYNC_ACTIVE' : 'OFFLINE'}
        </div>
      </header>

      <div className="intelligence-container">
        <div className="topology-grid">
          <div className="topology-node topology-node--local">
            <div className="topology-node__icon">💻</div>
            <div className="topology-node__label">LOCAL_SENTINEL</div>
          </div>
          
          <div className="topology-connections">
            {activeConnections.length === 0 ? (
              <div className="empty-state" style={{ padding: '100px 0' }}>
                <div className="empty-state__icon">🌐</div>
                <div className="empty-state__text">NO ACTIVE EXTERNAL CONNECTIONS</div>
              </div>
            ) : (
              activeConnections.map((conn, idx) => (
                <div key={`${conn.port}-${idx}`} className={`topology-link ${conn.risk_score >= 7 ? 'topology-link--high-risk' : ''}`}>
                  <div className="topology-link__rail">
                    <div className="topology-link__line topology-link__line--in">
                      {conn.kb_s_in > 0 && <div className="topology-link__flow topology-link__flow--in" />}
                    </div>
                    <div className="topology-link__line topology-link__line--out">
                      {conn.kb_s_out > 0 && <div className="topology-link__flow topology-link__flow--out" />}
                    </div>
                  </div>
                  <div className="topology-remote-card" style={{ border: conn.risk_score >= 7 ? '1px solid var(--accent-red)' : '1px solid var(--border-default)' }}>
                    <div className="topology-remote-card__header">
                      <span className="mono" style={{ fontWeight: 800, fontSize: '0.85rem' }}>{conn.remote_ip}</span>
                      <span>{conn.risk_score >= 10 ? '🚨' : conn.risk_score >= 5 ? '⚠️' : '✅'}</span>
                    </div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 700, marginBottom: '12px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {conn.org}
                    </div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', fontWeight: 800 }}>
                      <span style={{ color: 'var(--accent-blue)' }}>↓ {conn.kb_s_in.toFixed(1)}</span>
                      <span style={{ color: 'var(--accent-orange)' }}>↑ {conn.kb_s_out.toFixed(1)}</span>
                    </div>
                    <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', marginTop: '8px', borderTop: '1px solid var(--border-dim)', paddingTop: '8px' }}>
                      PORT: {conn.port} • {conn.app_name.toUpperCase()}
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default NetworkMapPage;
