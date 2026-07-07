/**
 * Sentinel — Professional Sidebar Navigation
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import { useTheme } from '../hooks/ThemeContext';

interface NavItem {
  to?: string;
  href?: string;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { href: 'http://localhost:3000', label: 'GRAFANA',     icon: '📊' },
  { to: '/processes',              label: 'PROCESSES',   icon: '⚙️' },
  { to: '/settings',               label: 'SETTINGS',    icon: '🔧' },
];

const Sidebar: React.FC = () => {
  const { theme, toggleTheme } = useTheme();

  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__logo-container">
          <div className="sidebar__logo">V</div>
          <div className="sidebar__brand-text">
            <h1 className="sidebar__title">VIGILANT</h1>
            <div style={{ fontSize: '0.65rem', fontWeight: 800, color: 'var(--text-muted)', letterSpacing: '0.1em' }}>THREAT_OPS</div>
          </div>
        </div>
      </div>

      <nav className="sidebar__nav">
        {NAV_ITEMS.map((item) => (
          item.href ? (
            <a
              key={item.label}
              href={item.href}
              target="_blank"
              rel="noopener noreferrer"
              className="sidebar__link"
            >
              <span style={{ fontSize: '1.1rem', width: '24px', textAlign: 'center' }}>{item.icon}</span>
              <span>{item.label}</span>
              <span style={{ marginLeft: 'auto', fontSize: '0.8rem', opacity: 0.5 }}>↗</span>
            </a>
          ) : (
            <NavLink
              key={item.to}
              to={item.to!}
              end={item.to === '/'}
              className={({ isActive }) =>
                `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`
              }
            >
              <span style={{ fontSize: '1.1rem', width: '24px', textAlign: 'center' }}>{item.icon}</span>
              <span>{item.label}</span>
            </NavLink>
          )
        ))}
      </nav>

      <div style={{ marginTop: 'auto', padding: '24px', borderTop: '1px solid var(--border-dim)' }}>
        <div style={{ fontSize: '0.6rem', color: 'var(--text-muted)', fontWeight: 800 }}>SYSTEM_ENCRYPTED</div>
        <div style={{ fontSize: '0.6rem', color: 'var(--accent-blue)', fontWeight: 800, margin: '4px 0 16px 0' }}>KERNEL_MODE_ACTIVE</div>
        <button 
          onClick={toggleTheme}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            width: '100%',
            padding: '8px 12px',
            background: 'var(--bg-glass)',
            border: '1px solid var(--border-dim)',
            borderRadius: '6px',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            fontWeight: 800,
            fontSize: '0.75rem',
            transition: 'all 0.2s'
          }}
        >
          <span>{theme === 'dark' ? '☀️' : '🌙'}</span>
          <span>{theme === 'dark' ? 'LIGHT MODE' : 'DARK MODE'}</span>
        </button>
      </div>
    </aside>
  );
};

export default Sidebar;
