/**
 * Sentinel — App Root
 *
 * Routing shell: sidebar + page outlet.
 * Uses react-router-dom BrowserRouter with all 5 routes.
 */

import React from 'react';
import { Routes, Route } from 'react-router-dom';
import { SocketProvider } from './hooks/SocketContext';
import Sidebar from './components/Sidebar';
import DashboardPage from './pages/DashboardPage';
import ProcessControlPage from './pages/ProcessControlPage';
import HistoricalLogsPage from './pages/HistoricalLogsPage';
import NetworkMapPage from './pages/NetworkMapPage';
import SettingsPage from './pages/SettingsPage';
const App: React.FC = () => {
  return (
    <SocketProvider>
      <div className="app-shell">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/processes" element={<ProcessControlPage />} />
            <Route path="/history" element={<HistoricalLogsPage />} />
            <Route path="/network" element={<NetworkMapPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </main>
      </div>
    </SocketProvider>
  );
};


export default App;
