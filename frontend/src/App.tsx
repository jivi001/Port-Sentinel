/**
 * Sentinel — App Root
 *
 * Routing shell: sidebar + page outlet.
 * Uses react-router-dom BrowserRouter with all 5 routes.
 */

import React, { Suspense, lazy } from 'react';
import { Routes, Route } from 'react-router-dom';
import { SocketProvider } from './hooks/SocketContext';
import Sidebar from './components/Sidebar';
import DashboardPage from './pages/DashboardPage';

const ProcessControlPage = lazy(() => import('./pages/ProcessControlPage'));
const HistoricalLogsPage = lazy(() => import('./pages/HistoricalLogsPage'));
const NetworkMapPage = lazy(() => import('./pages/NetworkMapPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));

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
    <SocketProvider>
      <div className="app-shell">
        <Sidebar />
        <main className="main-content">
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/processes" element={<ProcessControlPage />} />
              <Route path="/history" element={<HistoricalLogsPage />} />
              <Route path="/network" element={<NetworkMapPage />} />
              <Route path="/settings" element={<SettingsPage />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </SocketProvider>
  );
};


export default App;
