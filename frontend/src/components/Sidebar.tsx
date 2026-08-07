import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, Activity, History, ShieldAlert, Settings, 
  Globe, Shield, FileText, AlertTriangle 
} from 'lucide-react';

const Sidebar: React.FC = () => {
  return (
    <aside className="sidebar">
      <div className="sidebar__brand">
        <div className="sidebar__logo-container">
          <div className="sidebar__logo">V</div>
          <span className="sidebar__title">Vigilant</span>
        </div>
      </div>
      
      <div style={{ 
        padding: '0 24px', 
        fontSize: '0.65rem', 
        fontWeight: 800, 
        letterSpacing: '0.1em', 
        color: 'var(--text-muted)', 
        textTransform: 'uppercase',
        marginTop: '16px' 
      }}>
        Overview
      </div>
      
      <nav className="sidebar__nav" style={{ flex: 'none', paddingBottom: 0 }}>
        <NavLink 
          to="/" 
          className={({ isActive }) => `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`}
        >
          <LayoutDashboard size={18} />
          <span>Dashboard</span>
        </NavLink>
        <NavLink 
          to="/processes" 
          className={({ isActive }) => `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`}
        >
          <Activity size={18} />
          <span>Active Connections</span>
        </NavLink>
        <NavLink 
          to="/threats" 
          className={({ isActive }) => `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`}
        >
          <Globe size={18} />
          <span>Threat Map</span>
        </NavLink>
      </nav>

      <div style={{ 
        padding: '0 24px', 
        fontSize: '0.65rem', 
        fontWeight: 800, 
        letterSpacing: '0.1em', 
        color: 'var(--text-muted)', 
        textTransform: 'uppercase',
        marginTop: '16px' 
      }}>
        Enforcement
      </div>

      <nav className="sidebar__nav" style={{ flex: 'none', paddingBottom: 0 }}>
        <NavLink 
          to="/firewall" 
          className={({ isActive }) => `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`}
        >
          <Shield size={18} />
          <span>Firewall Rules</span>
        </NavLink>
        <NavLink 
          to="/rules" 
          className={({ isActive }) => `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`}
        >
          <ShieldAlert size={18} />
          <span>Policy Engine</span>
        </NavLink>
        <NavLink 
          to="/alerts" 
          className={({ isActive }) => `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`}
        >
          <AlertTriangle size={18} />
          <span>Approvals & Alerts</span>
        </NavLink>
      </nav>

      <div style={{ 
        padding: '0 24px', 
        fontSize: '0.65rem', 
        fontWeight: 800, 
        letterSpacing: '0.1em', 
        color: 'var(--text-muted)', 
        textTransform: 'uppercase',
        marginTop: '16px' 
      }}>
        System
      </div>

      <nav className="sidebar__nav">
        <NavLink 
          to="/reports" 
          className={({ isActive }) => `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`}
        >
          <FileText size={18} />
          <span>Reports</span>
        </NavLink>
        <NavLink 
          to="/history" 
          className={({ isActive }) => `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`}
        >
          <History size={18} />
          <span>Audit Log</span>
        </NavLink>
        <NavLink 
          to="/settings" 
          className={({ isActive }) => `sidebar__link ${isActive ? 'sidebar__link--active' : ''}`}
        >
          <Settings size={18} />
          <span>Settings</span>
        </NavLink>
      </nav>

      <div style={{
        marginTop: 'auto',
        padding: '16px 24px',
        borderTop: '1px solid var(--border-dim)',
        fontSize: '0.75rem',
        color: 'var(--text-muted)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        <span>Press <kbd style={{ background: 'var(--bg-surface)', padding: '2px 6px', borderRadius: '4px', border: '1px solid var(--border-dim)' }}>Ctrl+K</kbd></span>
        <span>v2.0.0</span>
      </div>
    </aside>
  );
};

export default Sidebar;
