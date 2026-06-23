/**
 * Vigilant — Professional 3D Global Threat View
 * 
 * Interactive 3D Earth visualization of cyber threats using react-globe.gl.
 * Features real-time geo-located traffic feeds, historical playbacks, 
 * severity filtering, and smooth flight camera controls.
 */

import React, { useState, useEffect, useMemo, useRef } from 'react';
import Globe from 'react-globe.gl';
import { apiService } from '../services/apiService';
import { Globe as GlobeIcon, Play, Pause, ZoomIn, ZoomOut, RotateCw, ShieldAlert } from 'lucide-react';

interface Threat {
  ip: string;
  city: string;
  country: string;
  latitude: number;
  longitude: number;
  risk: number;
  org: string;
  port: number;
  kb_s_in?: number;
  kb_s_out?: number;
}

interface TimelineEvent {
  timestamp: number;
  threats: Threat[];
}

// Coordinate of local security operations center (default center of US)
const LOCAL_COORDS = { lat: 39.8283, lng: -98.5795 };

const NetworkMapPage: React.FC = () => {
  const globeRef = useRef<any>();
  const [threats, setThreats] = useState<Threat[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [countries, setCountries] = useState<{ country: string; count: number }[]>([]);
  
  // Controls state
  const [minRisk, setMinRisk] = useState<number>(0);
  const [hours, setHours] = useState<number>(24);
  const [autoRotate, setAutoRotate] = useState<boolean>(true);
  const [selectedThreat, setSelectedThreat] = useState<Threat | null>(null);
  
  // Replay state
  const [isReplaying, setIsReplaying] = useState<boolean>(false);
  const [replayIndex, setReplayIndex] = useState<number>(0);
  const [replaySpeed, setReplaySpeed] = useState<number>(1000); // ms per step
  
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch threat data
  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [geoData, countryData, timelineData] = await Promise.all([
        apiService.getThreatGeo(minRisk),
        apiService.getThreatCountries(),
        apiService.getThreatTimeline(hours),
      ]);
      
      setThreats(geoData);
      setCountries(countryData.sort((a, b) => b.count - a.count));
      setTimeline(timelineData);
      
      if (timelineData.length > 0 && replayIndex >= timelineData.length) {
        setReplayIndex(timelineData.length - 1);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to fetch threat intelligence data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => {
      if (!isReplaying) {
        fetchData();
      }
    }, 5000); // refresh every 5 seconds
    
    return () => clearInterval(interval);
  }, [minRisk, hours, isReplaying]);

  // Replay timer
  useEffect(() => {
    let timer: any;
    if (isReplaying && timeline.length > 0) {
      timer = setInterval(() => {
        setReplayIndex((prev) => {
          if (prev >= timeline.length - 1) {
            return 0;
          }
          return prev + 1;
        });
      }, replaySpeed);
    }
    return () => clearInterval(timer);
  }, [isReplaying, timeline, replaySpeed]);

  // Active threats based on whether we are in active or replay mode
  const activeThreats = useMemo(() => {
    if (isReplaying && timeline[replayIndex]) {
      return timeline[replayIndex].threats.filter(t => t.risk >= minRisk);
    }
    return threats;
  }, [isReplaying, timeline, replayIndex, threats, minRisk]);

  // Construct arc connections data (threat coordinate -> local SOC coordinate)
  const arcData = useMemo(() => {
    return activeThreats.map((t, idx) => ({
      id: `${t.ip}-${idx}`,
      startLat: t.latitude,
      startLng: t.longitude,
      endLat: LOCAL_COORDS.lat,
      endLng: LOCAL_COORDS.lng,
      color: t.risk >= 8 ? 'var(--accent-red)' : t.risk >= 5 ? 'var(--accent-orange)' : 'var(--accent-blue)',
      name: `${t.ip} (${t.city}, ${t.country}) -> Local SOC on port ${t.port} (Risk: ${t.risk}/10)`,
      stroke: t.risk >= 8 ? 0.6 : 0.4,
    }));
  }, [activeThreats]);

  // Construct globe markers
  const markerData = useMemo(() => {
    return [
      // Always show local SOC
      {
        lat: LOCAL_COORDS.lat,
        lng: LOCAL_COORDS.lng,
        color: 'var(--accent-green)',
        radius: 0.8,
        label: 'LOCAL SECURITY OPERATIONS CENTER (SOC)',
        isLocal: true,
      },
      ...activeThreats.map(t => ({
        lat: t.latitude,
        lng: t.longitude,
        color: t.risk >= 8 ? 'var(--accent-red)' : t.risk >= 5 ? 'var(--accent-orange)' : 'var(--accent-blue)',
        radius: t.risk >= 8 ? 0.6 : 0.4,
        label: `${t.ip} - ${t.org} (Risk: ${t.risk})`,
        isLocal: false,
      })),
    ];
  }, [activeThreats]);

  // Handle auto rotation configuration on ref change
  useEffect(() => {
    if (globeRef.current) {
      globeRef.current.controls().autoRotate = autoRotate;
      globeRef.current.controls().autoRotateSpeed = 0.5;
    }
  }, [autoRotate]);

  // Camera flight control to fly to selected threat coordinate
  const flyToThreat = (threat: Threat) => {
    setSelectedThreat(threat);
    if (globeRef.current) {
      setAutoRotate(false);
      globeRef.current.pointOfView({
        lat: threat.latitude,
        lng: threat.longitude,
        altitude: 1.2
      }, 1000);
    }
  };

  const zoomIn = () => {
    if (globeRef.current) {
      const pov = globeRef.current.pointOfView();
      globeRef.current.pointOfView({
        ...pov,
        altitude: Math.max(0.4, pov.altitude - 0.3)
      }, 300);
    }
  };

  const zoomOut = () => {
    if (globeRef.current) {
      const pov = globeRef.current.pointOfView();
      globeRef.current.pointOfView({
        ...pov,
        altitude: Math.min(3.0, pov.altitude + 0.3)
      }, 300);
    }
  };

  const resetCamera = () => {
    if (globeRef.current) {
      globeRef.current.pointOfView({
        lat: 20.0,
        lng: 0.0,
        altitude: 2.0
      }, 800);
      setAutoRotate(true);
      setSelectedThreat(null);
    }
  };

  return (
    <div className="page-container" style={{ padding: 0, height: '100%', display: 'flex', flexDirection: 'column' }}>
      {error && (
        <div className="error-banner" style={{ margin: 'var(--space-md) var(--space-xl) 0' }}>
          ⚠ SYSTEM_FAULT: {error}
        </div>
      )}
      
      {loading && activeThreats.length === 0 && (
        <div style={{ position: 'absolute', inset: 0, background: 'rgba(4, 8, 16, 0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', fontWeight: 800 }}>FETCHING GLOBAL THREAT INTEL...</span>
        </div>
      )}
      
      {/* Top Banner Control Panel */}
      <header className="page-header" style={{ padding: 'var(--space-md) var(--space-xl)', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-default)', zIndex: 10 }}>
        <div>
          <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-sm)' }}>
            <GlobeIcon style={{ color: 'var(--accent-blue)' }} size={24} />
            3D Global Threat View
          </h1>
          <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: 600, marginTop: '2px' }}>
            {isReplaying ? `REPLAY MODE — ARCHIVE REPLAY INDEX ${replayIndex + 1}/${timeline.length}` : 'LIVE REAL-TIME INGESTION SYNC'}
          </p>
        </div>
        
        {/* Filters */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-md)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.7rem', fontWeight: 800, color: 'var(--text-muted)' }}>MIN RISK:</span>
            <select 
              value={minRisk} 
              onChange={(e) => setMinRisk(Number(e.target.value))}
              style={{ padding: '4px 8px', fontSize: '0.75rem' }}
            >
              <option value={0}>All Traffic</option>
              <option value={5}>Medium Risk (&gt;=5)</option>
              <option value={8}>High Risk (&gt;=8)</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.7rem', fontWeight: 800, color: 'var(--text-muted)' }}>LOOKBACK:</span>
            <select 
              value={hours} 
              onChange={(e) => setHours(Number(e.target.value))}
              style={{ padding: '4px 8px', fontSize: '0.75rem' }}
            >
              <option value={1}>Last Hour</option>
              <option value={6}>Last 6 Hours</option>
              <option value={24}>Last 24 Hours</option>
            </select>
          </div>

          <div className="btn-group">
            <button className={`btn btn--sm ${autoRotate ? 'btn--active' : ''}`} onClick={() => setAutoRotate(!autoRotate)} title="Toggle Rotation">
              <RotateCw size={14} />
            </button>
            <button className="btn btn--sm" onClick={zoomIn} title="Zoom In">
              <ZoomIn size={14} />
            </button>
            <button className="btn btn--sm" onClick={zoomOut} title="Zoom Out">
              <ZoomOut size={14} />
            </button>
            <button className="btn btn--sm" onClick={resetCamera} style={{ fontSize: '0.65rem', fontWeight: 800 }}>
              RESET
            </button>
          </div>
        </div>
      </header>

      {/* Main Layout Area */}
      <div style={{ flex: 1, display: 'flex', position: 'relative', overflow: 'hidden' }}>
        
        {/* Globe Container */}
        <div style={{ flex: 1, height: '100%', background: '#040810' }}>
          <Globe
            ref={globeRef}
            globeImageUrl="//unpkg.com/three-globe/example/img/earth-night.jpg"
            bumpImageUrl="//unpkg.com/three-globe/example/img/earth-topology.png"
            backgroundImageUrl="//unpkg.com/three-globe/example/img/night-sky.png"
            
            // Arcs Configuration
            arcsData={arcData}
            arcStartLat="startLat"
            arcStartLng="startLng"
            arcEndLat="endLat"
            arcEndLng="endLng"
            arcColor="color"
            arcDashLength={0.4}
            arcDashGap={0.2}
            arcDashAnimateTime={2000}
            arcStroke="stroke"
            
            // Points (Pins) Configuration
            pointsData={markerData}
            pointLat="lat"
            pointLng="lng"
            pointColor="color"
            pointRadius="radius"
            pointAltitude={0.02}
            
            // Labels Configuration
            labelsData={markerData}
            labelLat="lat"
            labelLng="lng"
            labelText="label"
            labelSize={0.4}
            labelColor={() => 'var(--text-primary)'}
            labelDotRadius={0.1}
            labelAltitude={0.03}
          />
        </div>

        {/* Left Floating Sidebar: Stats & Feeds */}
        <div style={{ 
          position: 'absolute', 
          left: 'var(--space-md)', 
          top: 'var(--space-md)', 
          bottom: 'var(--space-md)',
          width: '320px', 
          background: 'var(--bg-glass)', 
          border: '1px solid var(--border-default)', 
          borderRadius: 'var(--radius-lg)', 
          display: 'flex', 
          flexDirection: 'column', 
          boxShadow: 'var(--shadow-lg)', 
          backdropFilter: 'blur(8px)',
          zIndex: 5,
          overflow: 'hidden'
        }}>
          {/* Countries Distribution */}
          <div style={{ padding: 'var(--space-md)', borderBottom: '1px solid var(--border-dim)' }}>
            <h3 style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--text-secondary)', letterSpacing: '0.05em', marginBottom: 'var(--space-sm)', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ShieldAlert size={14} style={{ color: 'var(--accent-red)' }} />
              TOP THREAT SOURCES
            </h3>
            {countries.length === 0 ? (
              <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>No source logs found.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {countries.slice(0, 4).map((c, i) => (
                  <div key={c.country} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{ color: 'var(--text-muted)', fontWeight: 800 }}>#{i+1}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{c.country}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, justifyContent: 'flex-end' }}>
                      <div style={{ height: '4px', background: 'var(--accent-blue-dim)', width: '60px', borderRadius: '2px', overflow: 'hidden', position: 'relative' }}>
                        <div style={{ position: 'absolute', left: 0, top: 0, bottom: 0, background: 'var(--accent-blue)', width: `${Math.min(100, (c.count / (countries[0]?.count || 1)) * 100)}%` }} />
                      </div>
                      <span style={{ fontWeight: 800, fontFamily: 'var(--font-mono)' }}>{c.count}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Active Logs / Threats List */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ padding: 'var(--space-sm) var(--space-md)', background: 'rgba(0,0,0,0.1)', borderBottom: '1px solid var(--border-dim)' }}>
              <h3 style={{ fontSize: '0.7rem', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
                ACTIVE INGESTION FEED ({activeThreats.length})
              </h3>
            </div>
            
            <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--space-sm)' }}>
              {activeThreats.length === 0 ? (
                <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                  No threats meet filters
                </div>
              ) : (
                activeThreats.map((t, idx) => (
                  <div 
                    key={`${t.ip}-${idx}`}
                    onClick={() => flyToThreat(t)}
                    style={{
                      padding: '8px 10px',
                      borderRadius: 'var(--radius-sm)',
                      background: selectedThreat?.ip === t.ip ? 'var(--bg-active)' : 'transparent',
                      border: `1px solid ${selectedThreat?.ip === t.ip ? 'var(--accent-blue)' : 'transparent'}`,
                      cursor: 'pointer',
                      marginBottom: '4px',
                      transition: 'all 150ms ease'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: '0.75rem', color: t.risk >= 8 ? 'var(--accent-red)' : 'var(--text-primary)' }}>
                        {t.ip}
                      </span>
                      <span style={{ 
                        fontSize: '0.6rem', 
                        padding: '1px 4px', 
                        borderRadius: '3px',
                        background: t.risk >= 8 ? 'var(--accent-red-dim)' : t.risk >= 5 ? 'var(--accent-orange-dim)' : 'var(--accent-blue-dim)',
                        color: t.risk >= 8 ? 'var(--accent-red)' : t.risk >= 5 ? 'var(--accent-orange)' : 'var(--accent-blue)',
                        fontWeight: 800
                      }}>
                        R:{t.risk}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-secondary)', marginTop: '2px', display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', maxWidth: '170px' }}>
                        {t.org}
                      </span>
                      <span style={{ color: 'var(--text-muted)', fontWeight: 700 }}>
                        {t.city}, {t.country}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Selected Threat Floating Card */}
        {selectedThreat && (
          <div style={{
            position: 'absolute',
            right: 'var(--space-md)',
            top: 'var(--space-md)',
            width: '300px',
            background: 'var(--bg-glass)',
            border: '1px solid var(--accent-blue)',
            borderRadius: 'var(--radius-lg)',
            padding: 'var(--space-md)',
            boxShadow: 'var(--shadow-lg)',
            backdropFilter: 'blur(8px)',
            zIndex: 5
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid var(--border-dim)', paddingBottom: '8px', marginBottom: '8px' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 800, color: 'var(--text-primary)' }}>Threat Details</span>
              <button 
                onClick={() => setSelectedThreat(null)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontWeight: 900 }}
              >
                ✕
              </button>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.75rem' }}>
              <div>
                <span style={{ color: 'var(--text-muted)', fontWeight: 800 }}>SOURCE IP:</span>
                <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, color: selectedThreat.risk >= 8 ? 'var(--accent-red)' : 'var(--text-primary)' }}>{selectedThreat.ip}</p>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontWeight: 800 }}>ORGANIZATION:</span>
                <p style={{ fontWeight: 700 }}>{selectedThreat.org}</p>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
                <div>
                  <span style={{ color: 'var(--text-muted)', fontWeight: 800 }}>LOCATION:</span>
                  <p style={{ fontWeight: 700 }}>{selectedThreat.city}, {selectedThreat.country}</p>
                </div>
                <div>
                  <span style={{ color: 'var(--text-muted)', fontWeight: 800 }}>TARGET PORT:</span>
                  <p style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, color: 'var(--accent-blue)' }}>{selectedThreat.port}</p>
                </div>
              </div>
              <div>
                <span style={{ color: 'var(--text-muted)', fontWeight: 800 }}>COORDINATES:</span>
                <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem' }}>{selectedThreat.latitude.toFixed(4)}, {selectedThreat.longitude.toFixed(4)}</p>
              </div>
              
              <div style={{ display: 'flex', gap: 'var(--space-sm)', marginTop: '8px' }}>
                <button className="btn btn--danger" style={{ flex: 1, padding: '4px 8px', fontSize: '0.65rem' }} onClick={() => apiService.blockPort(selectedThreat.port)}>
                  BLOCK PORT
                </button>
                <button className="btn btn--sm" style={{ flex: 1, padding: '4px 8px', fontSize: '0.65rem' }} onClick={() => apiService.requestApproval(0, selectedThreat.ip, `Investigate IP Threat: ${selectedThreat.ip}`)}>
                  REQUEST ACTION
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Bottom Floating Playback / Replay Bar */}
        <div style={{
          position: 'absolute',
          left: '50%',
          transform: 'translateX(-50%)',
          bottom: 'var(--space-lg)',
          width: '540px',
          background: 'var(--bg-glass)',
          border: '1px solid var(--border-default)',
          borderRadius: 'var(--radius-xl)',
          padding: '12px var(--space-lg)',
          boxShadow: 'var(--shadow-lg)',
          backdropFilter: 'blur(8px)',
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-md)',
          zIndex: 5
        }}>
          <button 
            className={`btn ${isReplaying ? 'btn--active' : 'btn--primary'}`}
            onClick={() => {
              setIsReplaying(!isReplaying);
              setSelectedThreat(null);
            }}
            style={{ padding: '6px 12px' }}
          >
            {isReplaying ? <Pause size={14} /> : <Play size={14} />}
            <span style={{ fontSize: '0.7rem', fontWeight: 800 }}>{isReplaying ? 'PAUSE REPLAY' : 'PLAY REPLAY'}</span>
          </button>
          
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <input 
              type="range" 
              min={0} 
              max={Math.max(0, timeline.length - 1)} 
              value={replayIndex}
              onChange={(e) => {
                setReplayIndex(Number(e.target.value));
                setIsReplaying(false);
              }}
              style={{ width: '100%', cursor: 'pointer' }}
              disabled={timeline.length <= 1}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', color: 'var(--text-muted)', fontWeight: 800 }}>
              <span>{timeline.length > 0 ? new Date(timeline[0].timestamp * 1000).toLocaleTimeString() : '00:00:00'}</span>
              <span style={{ color: 'var(--text-secondary)' }}>
                {timeline[replayIndex] ? new Date(timeline[replayIndex].timestamp * 1000).toLocaleTimeString() : 'PLAYBACK TIMELINE'}
              </span>
              <span>{timeline.length > 0 ? new Date(timeline[timeline.length - 1].timestamp * 1000).toLocaleTimeString() : '00:00:00'}</span>
            </div>
          </div>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', alignItems: 'center' }}>
            <span style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontWeight: 800 }}>SPEED</span>
            <select 
              value={replaySpeed} 
              onChange={(e) => setReplaySpeed(Number(e.target.value))}
              style={{ padding: '2px 4px', fontSize: '0.65rem' }}
            >
              <option value={2000}>0.5x</option>
              <option value={1000}>1.0x</option>
              <option value={500}>2.0x</option>
              <option value={250}>4.0x</option>
            </select>
          </div>
        </div>

      </div>
    </div>
  );
};

export default NetworkMapPage;
