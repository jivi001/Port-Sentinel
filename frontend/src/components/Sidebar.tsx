/**
 * Sentinel — Sidebar Navigation
 *
 * Collapsible sidebar with icon + text navigation links.
 * Active route is highlighted. Collapse toggle at bottom.
 */

import React, { useState } from 'react';
import { NavLink } from 'react-router-dom';

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

const NAV_ITEMS: NavItem[] = [
  { to: '/',          label: 'Dashboard',       icon: '📊' },
  { to: '/processes', label: 'Process Control',  icon: '⚙️' },
  { to: '/history',   label: 'Historical Logs',  icon: '📈' },
  { to: '/network',   label: 'Network Map',      icon: '🌐' },
  { to: '/settings',  label: 'Settings',         icon: '🔧' },
];

const Sidebar: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside className={`sidebar ${collapsed ? 'sidebar--collapsed' : ''}`} id="sidebar">
      {/* Brand */}
      <div className="sidebar__brand">
        <div className="sidebar__logo">P</div>
        {!collapsed && (
          <div className="sidebar__brand-text">
            <div className="sidebar__title">Sentinel</div>
            <div className="sidebar__subtitle">Network Sentinel</div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="sidebar__nav">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`
            }
            title={collapsed ? item.label : undefined}
          >
            <span className="sidebar__link-icon">{item.icon}</span>
            {!collapsed && <span className="sidebar__link-label">{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Collapse Toggle */}
      <button
        className="sidebar__toggle"
        onClick={() => setCollapsed((c) => !c)}
        title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        id="sidebar-toggle"
      >
        <span className="sidebar__toggle-icon">
          {collapsed ? '▶' : '◀'}
        </span>
        {!collapsed && <span>Collapse</span>}
      </button>
    </aside>
  );
};

export default Sidebar;
