/**
 * Sentinel — Professional Sidebar Navigation
 */

import React from 'react';
import { NavLink } from 'react-router-dom';

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/',          label: 'DASHBOARD',       icon: '📊' },
  { to: '/processes', label: 'PROCESSES',       icon: '⚙️' },
  { to: '/history',   label: 'FORENSICS',       icon: '📈' },
  { to: '/network',   label: 'INTELLIGENCE',    icon: '🌐' },
  { to: '/settings',  label: 'SETTINGS',        icon: '🔧' },
];

const Sidebar: React.FC = () => {
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__logo-container">
          <div className="sidebar__logo">S</div>
          <div className="sidebar__brand-text">
            <h1 className="sidebar__title">SENTINEL</h1>
            <div style={{ fontSize: '0.65rem', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.1em' }}>NETWORK_OPS</div>
          </div>
        </div>
      </div>

      <nav className="sidebar__nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`
            }
          >
            <span style={{ fontSize: '1.1rem', width: '24px', textAlign: 'center' }}>{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div style={{ marginTop: 'auto', padding: '24px', borderTop: '1px solid var(--border-dim)' }}>
        <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontWeight: 800 }}>SYSTEM_ENCRYPTED</div>
        <div style={{ fontSize: '0.6rem', color: 'var(--accent-blue)', fontWeight: 800, marginTop: '4px' }}>KERNEL_MODE_ACTIVE</div>
      </div>
    </aside>
  );
};

export default Sidebar;
