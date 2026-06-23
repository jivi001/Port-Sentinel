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
    <aside className="w-64 bg-surface border-r border-gray-800 flex flex-col shrink-0">
      <div className="p-6 border-b border-gray-800 flex items-center gap-3">
        <div className="w-10 h-10 bg-primary/10 border border-primary/30 rounded-lg flex items-center justify-center text-primary font-bold text-xl shadow-[0_0_15px_rgba(59,130,246,0.3)]">
          S
        </div>
        <div>
          <h1 className="text-white font-black text-xl tracking-wider leading-none">SENTINEL</h1>
          <div className="text-[0.65rem] font-bold text-gray-500 tracking-[0.1em] mt-1">NETWORK_OPS</div>
        </div>
      </div>

      <nav className="flex-1 py-6 px-4 flex flex-col gap-2">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-3 rounded-lg font-bold text-xs tracking-widest transition-all duration-300 ${
                isActive 
                  ? 'bg-primary/10 text-primary border border-primary/30 shadow-[0_0_10px_rgba(59,130,246,0.1)]' 
                  : 'text-gray-400 hover:text-white hover:bg-white/5 border border-transparent'
              }`
            }
          >
            <span className="text-lg w-6 text-center">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </nav>

      <div className="mt-auto p-6 border-t border-gray-800">
        <div className="text-[0.6rem] text-gray-500 font-bold tracking-widest">SYSTEM_ENCRYPTED</div>
        <div className="text-[0.6rem] text-primary font-bold tracking-widest mt-1">KERNEL_MODE_ACTIVE</div>
      </div>
    </aside>
  );
};

export default Sidebar;
