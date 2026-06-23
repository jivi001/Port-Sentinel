/**
 * Sentinel — Professional Network Intelligence
 * 
 * Clean, logical Network Topology visualization.
 * Hardcoded to Cyber Midnight design language.
 */

import React, { useMemo } from 'react';
import { useSocketContext } from '../hooks/SocketContext';
import Globe from 'react-globe.gl';

// Helper to deterministically generate lat/lng from IP for demo purposes
// In production, this would use MaxMind GeoIP on the backend.
function ipToCoords(ip: string): { lat: number, lng: number } {
  if (!ip || ip === "0.0.0.0") return { lat: 0, lng: 0 };
  let hash = 0;
  for (let i = 0; i < ip.length; i++) {
    hash = ((hash << 5) - hash) + ip.charCodeAt(i);
    hash |= 0;
  }
  
  // Random deterministic lat (-90 to 90) and lng (-180 to 180)
  const lat = (Math.abs(hash) % 18000) / 100 - 90;
  const lng = (Math.abs(hash * 31) % 36000) / 100 - 180;
  return { lat, lng };
}

const NetworkMapPage: React.FC = () => {
  const { portTable, connected } = useSocketContext();

  const globeData = useMemo(() => {
    return portTable
      .filter(p => p.remote_ip !== "0.0.0.0" && p.remote_ip)
      .map(p => {
        const coords = ipToCoords(p.remote_ip);
        return {
          ...p,
          lat: coords.lat,
          lng: coords.lng,
          color: p.risk_score >= 7 ? '#ef4444' : p.risk_score >= 4 ? '#f59e0b' : '#3b82f6'
        };
      });
  }, [portTable]);

  return (
    <div className="page-container h-full w-full flex flex-col">
      <header className="page-header flex justify-between items-center mb-4 shrink-0">
        <h1 className="page-title text-3xl font-bold text-text-main tracking-tight">Global Threat Intelligence</h1>
        <div className={`connection-badge ${connected ? 'text-accent' : 'text-danger'} flex items-center gap-2 px-4 py-2 bg-surface rounded-full border border-border-main`}>
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-accent animate-pulse' : 'bg-danger'}`} />
          {connected ? 'TOPOLOGY_SYNC_ACTIVE' : 'OFFLINE'}
        </div>
      </header>

      <div className="bg-surface border border-border-main rounded-xl flex-1 flex overflow-hidden relative shadow-lg">
        {/* React Globe */}
        <div className="absolute inset-0 flex items-center justify-center">
          <Globe
            globeImageUrl="//unpkg.com/three-globe/example/img/earth-dark.jpg"
            bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"
            backgroundImageUrl="//unpkg.com/three-globe/example/img/night-sky.png"
            pointsData={globeData}
            pointAltitude={(d: any) => (d.kb_s_in + d.kb_s_out) / 5000 + 0.05}
            pointColor="color"
            pointRadius={0.5}
            pointsMerge={true}
            arcsData={globeData.map(d => ({
              startLat: 37.7749, // Assuming local host is SF for demo
              startLng: -122.4194,
              endLat: d.lat,
              endLng: d.lng,
              color: d.color
            }))}
            arcColor="color"
            arcDashLength={0.4}
            arcDashGap={0.2}
            arcDashAnimateTime={1500}
            labelsData={globeData}
            labelLat={(d: any) => d.lat}
            labelLng={(d: any) => d.lng}
            labelText={(d: any) => d.remote_ip}
            labelSize={1.5}
            labelDotRadius={0.5}
            labelColor={() => 'rgba(255,255,255,0.75)'}
            labelResolution={2}
          />
        </div>

        {/* Overlay Overlay Cards */}
        <div className="absolute top-4 right-4 w-80 max-h-[90%] overflow-y-auto flex flex-col gap-3 z-10 pointer-events-auto custom-scrollbar">
          {globeData.length === 0 ? (
            <div className="bg-surface/80 backdrop-blur-md p-6 rounded-lg border border-border-main text-center text-text-muted">
              NO ACTIVE EXTERNAL CONNECTIONS
            </div>
          ) : (
            globeData.map((conn, idx) => (
              <div key={`${conn.port}-${idx}`} className={`bg-surface/90 backdrop-blur-md p-4 rounded-lg border ${conn.risk_score >= 7 ? 'border-danger/50' : 'border-border-main'} transition-transform hover:-translate-y-1`}>
                <div className="flex justify-between items-center mb-2">
                  <span className="font-mono text-sm font-bold text-text-main">{conn.remote_ip}</span>
                  <span>{conn.risk_score >= 10 ? '🚨' : conn.risk_score >= 5 ? '⚠️' : '✅'}</span>
                </div>
                <div className="text-xs text-text-muted font-bold mb-3 truncate">
                  {conn.org}
                </div>
                <div className="flex justify-between text-xs font-bold">
                  <span className="text-primary">↓ {conn.kb_s_in.toFixed(1)} KB/s</span>
                  <span className="text-warning">↑ {conn.kb_s_out.toFixed(1)} KB/s</span>
                </div>
                <div className="text-[10px] text-text-dim mt-2 pt-2 border-t border-border-main">
                  PORT: {conn.port} • {conn.app_name.toUpperCase()}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default NetworkMapPage;
