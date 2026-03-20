/**
 * Sentinel — Network Map Page (Placeholder)
 *
 * Coming-soon placeholder with animated world outline.
 * Full geo-IP mapping will be added when a geo-IP service is configured.
 */

import React from 'react';

const NetworkMapPage: React.FC = () => {
  return (
    <>
      <div className="page-header">
        <h1 className="page-title">Global Network Map</h1>
      </div>

      <div className="network-map-placeholder">
        <div className="network-map-placeholder__globe">
          {/* Animated SVG globe outline */}
          <svg
            viewBox="0 0 200 200"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className="globe-svg"
          >
            {/* Outer circle */}
            <circle cx="100" cy="100" r="90" stroke="var(--accent-blue)" strokeWidth="1" opacity="0.3" />
            {/* Latitude lines */}
            <ellipse cx="100" cy="100" rx="90" ry="30" stroke="var(--accent-blue)" strokeWidth="0.5" opacity="0.2" />
            <ellipse cx="100" cy="100" rx="90" ry="60" stroke="var(--accent-blue)" strokeWidth="0.5" opacity="0.15" />
            {/* Longitude lines */}
            <ellipse cx="100" cy="100" rx="30" ry="90" stroke="var(--accent-blue)" strokeWidth="0.5" opacity="0.2" />
            <ellipse cx="100" cy="100" rx="60" ry="90" stroke="var(--accent-blue)" strokeWidth="0.5" opacity="0.15" />
            {/* Center dot */}
            <circle cx="100" cy="100" r="3" fill="var(--accent-blue)" opacity="0.6">
              <animate attributeName="r" values="3;6;3" dur="2s" repeatCount="indefinite" />
              <animate attributeName="opacity" values="0.6;0.2;0.6" dur="2s" repeatCount="indefinite" />
            </circle>
            {/* Connection dots */}
            <circle cx="60" cy="70" r="2" fill="var(--accent-cyan)" opacity="0.5">
              <animate attributeName="opacity" values="0.5;1;0.5" dur="3s" repeatCount="indefinite" />
            </circle>
            <circle cx="140" cy="80" r="2" fill="var(--accent-orange)" opacity="0.5">
              <animate attributeName="opacity" values="0.5;1;0.5" dur="2.5s" repeatCount="indefinite" />
            </circle>
            <circle cx="120" cy="130" r="2" fill="var(--accent-green)" opacity="0.5">
              <animate attributeName="opacity" values="0.5;1;0.5" dur="3.5s" repeatCount="indefinite" />
            </circle>
            {/* Connection arcs */}
            <path d="M100 100 Q80 60 60 70" stroke="var(--accent-cyan)" strokeWidth="0.5" opacity="0.3" fill="none">
              <animate attributeName="opacity" values="0.1;0.5;0.1" dur="3s" repeatCount="indefinite" />
            </path>
            <path d="M100 100 Q130 70 140 80" stroke="var(--accent-orange)" strokeWidth="0.5" opacity="0.3" fill="none">
              <animate attributeName="opacity" values="0.1;0.5;0.1" dur="2.5s" repeatCount="indefinite" />
            </path>
            <path d="M100 100 Q115 120 120 130" stroke="var(--accent-green)" strokeWidth="0.5" opacity="0.3" fill="none">
              <animate attributeName="opacity" values="0.1;0.5;0.1" dur="3.5s" repeatCount="indefinite" />
            </path>
          </svg>
        </div>

        <div className="network-map-placeholder__text">
          <h2 className="network-map-placeholder__title">Coming Soon</h2>
          <p className="network-map-placeholder__desc">
            Geographic visualization of network connections will be available
            when a geo-IP service is configured. Connect an API like ipinfo.io
            or MaxMind GeoLite2 to see where your traffic flows across the globe.
          </p>
        </div>
      </div>
    </>
  );
};

export default NetworkMapPage;
