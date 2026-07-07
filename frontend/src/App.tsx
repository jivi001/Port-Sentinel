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
import { Navigate } from 'react-router-dom';

const ProcessControlPage = lazy(() => import('./pages/ProcessControlPage'));

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
              <Route path="/" element={<Navigate to="/processes" replace />} />
              <Route path="/processes" element={<ProcessControlPage />} />

              <Route path="/settings" element={<SettingsPage />} />
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
  );
};

export default App;
