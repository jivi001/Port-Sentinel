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
  <div className="flex items-center justify-center min-h-[40vh] w-full">
    <span className="text-gray-500 text-sm font-bold tracking-widest animate-pulse">LOADING_MODULE...</span>
  </div>
);

const App: React.FC = () => {
  return (
    <SocketProvider>
      <div className="flex h-screen w-screen bg-background overflow-hidden font-sans text-gray-100">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6 bg-background relative z-0">
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/processes" element={<ProcessControlPage />} />
              <Route path="/history" element={<HistoricalLogsPage />} />
              <Route path="/network" element={<NetworkMapPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="*" element={
                <div className="flex flex-col items-center justify-center h-full text-gray-500">
                  <h1 className="text-6xl font-black text-danger mb-4">404</h1>
                  <p className="font-bold tracking-widest uppercase">MODULE NOT FOUND</p>
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
