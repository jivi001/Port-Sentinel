import React from 'react';
import { useLocation, Link } from 'react-router-dom';
import { ChevronRight, Home } from 'lucide-react';

const routeNames: Record<string, string> = {
  '/': 'Dashboard',
  '/processes': 'Active Connections',
  '/threats': 'Threat Map',
  '/firewall': 'Firewall Rules',
  '/rules': 'Policy Engine',
  '/alerts': 'Approvals & Alerts',
  '/reports': 'Compliance Reports',
  '/history': 'Audit Log',
  '/settings': 'Settings',
};

export const Breadcrumbs: React.FC = () => {
  const location = useLocation();
  const pathnames = location.pathname.split('/').filter(x => x);

  // If we are at root, no need to show complex breadcrumbs
  if (pathnames.length === 0) {
    return (
      <nav style={{ display: 'flex', alignItems: 'center', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
        <Home size={14} style={{ marginRight: '6px' }} />
        <span>Dashboard</span>
      </nav>
    );
  }

  return (
    <nav style={{ display: 'flex', alignItems: 'center', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
      <Link to="/" style={{ color: 'inherit', textDecoration: 'none', display: 'flex', alignItems: 'center' }}>
        <Home size={14} />
      </Link>
      
      {pathnames.map((value, index) => {
        const to = `/${pathnames.slice(0, index + 1).join('/')}`;
        const isLast = index === pathnames.length - 1;
        const name = routeNames[to] || value;

        return (
          <React.Fragment key={to}>
            <ChevronRight size={14} style={{ margin: '0 6px', opacity: 0.5 }} />
            {isLast ? (
              <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{name}</span>
            ) : (
              <Link to={to} style={{ color: 'inherit', textDecoration: 'none' }}>
                {name}
              </Link>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
};
