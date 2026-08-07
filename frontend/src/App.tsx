import React, { Suspense, lazy } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { SocketProvider } from './hooks/SocketContext';
import { ToastProvider } from './components/ui/Toast';
import { CommandPalette } from './components/CommandPalette';
import Sidebar from './components/Sidebar';
import DashboardPage from './pages/DashboardPage';

const ProcessControlPage = lazy(() => import('./pages/ProcessControlPage'));
const HistoricalLogsPage = lazy(() => import('./pages/HistoricalLogsPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));

// New Routes
const NetworkMapPage = lazy(() => import('./pages/NetworkMapPage'));
const FirewallPage = lazy(() => import('./pages/FirewallPage'));
const RulesPage = lazy(() => import('./pages/RulesPage'));
const AlertsPage = lazy(() => import('./pages/AlertsPage'));
const ReportsPage = lazy(() => import('./pages/ReportsPage'));

const RouteFallback: React.FC = () => (
  <div
    className="page-container"
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '40vh',
    }}
  >
    <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>Loading…</span>
  </div>
);

const App: React.FC = () => {
  return (
    <ToastProvider>
      <SocketProvider>
        <div className="app-shell">
          <Sidebar />
          <CommandPalette />
          <main className="main-content">
            <Suspense fallback={<RouteFallback />}>
              <Routes>
                <Route path="/" element={<DashboardPage />} />
                <Route path="/processes" element={<ProcessControlPage />} />
                <Route path="/history" element={<HistoricalLogsPage />} />
                <Route path="/settings" element={<SettingsPage />} />
                
                {/* New Routes */}
                <Route path="/threats" element={<NetworkMapPage />} />
                <Route path="/network-map" element={<Navigate to="/threats" replace />} />
                <Route path="/firewall" element={<FirewallPage />} />
                <Route path="/rules" element={<RulesPage />} />
                <Route path="/alerts" element={<AlertsPage />} />
                <Route path="/reports" element={<ReportsPage />} />

                <Route path="*" element={
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)' }}>
                    <h1 style={{ fontSize: '4rem', margin: 0, color: 'var(--accent-red)' }}>404</h1>
                    <p>MODULE NOT FOUND</p>
                  </div>
                } />
              </Routes>
            </Suspense>
          </main>
        </div>
      </SocketProvider>
    </ToastProvider>
  );
};

export default App;
