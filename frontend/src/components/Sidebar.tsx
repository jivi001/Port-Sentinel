import React from 'react';
import { NavLink } from 'react-router-dom';

const Sidebar: React.FC = () => {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>Vigilant</h2>
      </div>
      <nav className="sidebar-nav">
        <NavLink to="/processes" className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}>
          Process Control
        </NavLink>
        <NavLink to="/settings" className={({ isActive }) => isActive ? "nav-item active" : "nav-item"}>
          Settings
        </NavLink>
        <a href="http://localhost:3000" target="_blank" rel="noopener noreferrer" className="nav-item">
          Grafana
        </a>
      </nav>
    </aside>
  );
};

export default Sidebar;
