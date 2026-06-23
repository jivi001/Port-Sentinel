/**
 * Sentinel — Professional Forensics & Analyst Approvals Page
 */

import React, { useState, useCallback, useEffect } from 'react';
import { AreaChart, Area, ResponsiveContainer, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts';
import { useSocketContext } from '../hooks/SocketContext';
import { apiService } from '../services/apiService';

const TIME_RANGES = [
  { label: '1H', hours: 1 },
  { label: '6H', hours: 6 },
  { label: '24H', hours: 24 },
];

const HistoricalLogsPage: React.FC = () => {
  const { portTable } = useSocketContext();
  const [selectedPort, setSelectedPort] = useState<number | null>(null);
  const [selectedRange, setSelectedRange] = useState(1);
  const [history, setHistory] = useState<any[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [approvals, setApprovals] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'audit' | 'approvals'>('audit');

  const fetchHistory = useCallback(async () => {
    if (selectedPort == null) return;
    setLoading(true);
    try {
      const data = await apiService.getPortHistory(selectedPort, selectedRange);
      setHistory(data);
    } catch (e) {
      console.error(e);
    } finally { setLoading(false); }
  }, [selectedPort, selectedRange]);

  const fetchAuditLogs = useCallback(async () => {
    try {
      const data = await apiService.getAuditLogs(50);
      setAuditLogs(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  const fetchApprovals = useCallback(async () => {
    try {
      const data = await apiService.getApprovals();
      setApprovals(data);
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    fetchAuditLogs();
    fetchApprovals();
    if (selectedPort != null) fetchHistory();
  }, [selectedPort, selectedRange, fetchHistory, fetchAuditLogs, fetchApprovals]);

  const handleResolve = async (id: number, status: 'approved' | 'rejected') => {
    try {
      await apiService.resolveApproval(id, status);
      fetchApprovals();
      fetchAuditLogs();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="page-container h-full w-full flex flex-col">
      <header className="page-header flex justify-between items-center mb-4 shrink-0">
        <h1 className="page-title text-3xl font-bold text-white tracking-tight">Forensic Analysis</h1>
        <div className="flex gap-4 items-center">
          <div className="flex bg-gray-900 p-1 rounded-lg border border-gray-800">
            {TIME_RANGES.map((r) => (
              <button 
                key={r.hours} 
                className={`px-4 py-1.5 rounded-md text-xs font-bold transition-colors ${selectedRange === r.hours ? 'bg-primary text-white' : 'text-gray-400 hover:text-white hover:bg-white/5'}`}
                onClick={() => setSelectedRange(r.hours)}
              >{r.label}</button>
            ))}
          </div>
          <select 
            className="bg-secondary border border-gray-800 text-white px-4 py-2 rounded-lg text-sm font-bold focus:outline-none focus:border-primary"
            value={selectedPort ?? ''} 
            onChange={(e) => setSelectedPort(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">SELECT PORT...</option>
            {[...new Set(portTable.map(p => p.port))].sort((a,b) => a-b).map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          {loading && (
            <span className="text-gray-400 text-xs tracking-widest font-bold animate-pulse">LOADING_HISTORY</span>
          )}
        </div>
      </header>

      {/* Traffic Visualization */}
      {selectedPort && history.length > 0 && (
        <section className="bg-surface border border-gray-800 rounded-xl shadow-lg mb-6 shrink-0 overflow-hidden">
          <div className="p-4 bg-gray-900 border-b border-gray-800">
            <h2 className="text-xs font-bold text-gray-400 uppercase tracking-widest">Port {selectedPort} Throughput</h2>
          </div>
          <div className="w-full h-48 p-4">
            <ResponsiveContainer>
              <AreaChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" vertical={false} />
                <XAxis dataKey="timestamp" hide />
                <YAxis hide />
                <Tooltip contentStyle={{ background: '#111827', border: '1px solid #1F2937', borderRadius: '8px' }} />
                <Area type="monotone" dataKey="kb_s_in" stroke="#3B82F6" fill="#3B82F6" fillOpacity={0.1} isAnimationActive={false} />
                <Area type="monotone" dataKey="kb_s_out" stroke="#F59E0B" fill="#F59E0B" fillOpacity={0.1} isAnimationActive={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Logs and Approvals */}
      <section className="bg-surface border border-gray-800 rounded-xl shadow-lg flex flex-col flex-1 min-h-0 overflow-hidden">
        <div className="p-4 bg-gray-900 border-b border-gray-800 flex justify-between items-center">
          <div className="flex gap-4">
            <button 
              className={`text-xs font-bold uppercase tracking-widest pb-1 border-b-2 transition-colors ${activeTab === 'audit' ? 'text-primary border-primary' : 'text-gray-500 border-transparent hover:text-gray-300'}`}
              onClick={() => setActiveTab('audit')}
            >
              Security Events Audit
            </button>
            <button 
              className={`text-xs font-bold uppercase tracking-widest pb-1 border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'approvals' ? 'text-primary border-primary' : 'text-gray-500 border-transparent hover:text-gray-300'}`}
              onClick={() => setActiveTab('approvals')}
            >
              Pending Approvals
              {approvals.length > 0 && <span className="bg-warning text-white px-1.5 py-0.5 rounded-full text-[10px]">{approvals.length}</span>}
            </button>
          </div>
          <button className="text-xs font-bold text-gray-400 hover:text-white transition-colors" onClick={() => { fetchAuditLogs(); fetchApprovals(); }}>REFRESH</button>
        </div>

        {activeTab === 'audit' && (
          <div className="flex-1 flex flex-col min-h-0">
            <div className="flex items-center p-4 bg-secondary border-b border-gray-800 text-xs font-bold text-gray-500 uppercase tracking-widest gap-4">
              <div className="w-24">TIMESTAMP</div>
              <div className="w-32">EVENT</div>
              <div className="w-48">TARGET</div>
              <div className="w-24">SEVERITY</div>
              <div className="flex-1">MESSAGE</div>
            </div>
            <div className="flex-1 overflow-y-auto">
              {auditLogs.length === 0 ? (
                <div className="p-16 text-center text-gray-500 text-sm font-bold tracking-wider">NO SECURITY EVENTS DETECTED</div>
              ) : (
                auditLogs.map((log) => (
                  <div key={log.id} className="flex items-center p-4 border-b border-gray-800 hover:bg-gray-800/50 transition-colors gap-4">
                    <div className="w-24 font-mono text-xs text-gray-500">{new Date(log.timestamp * 1000).toLocaleTimeString()}</div>
                    <div className="w-32 font-mono text-xs text-primary">{log.event_type.toUpperCase()}</div>
                    <div className="w-48 font-mono text-xs text-white truncate">{log.app_name || `PORT ${log.port}`}</div>
                    <div className={`w-24 font-mono text-xs font-bold ${log.severity === 'critical' ? 'text-danger' : log.severity === 'warning' ? 'text-warning' : 'text-accent'}`}>{log.severity.toUpperCase()}</div>
                    <div className="flex-1 text-sm text-gray-300 truncate">{log.message}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {activeTab === 'approvals' && (
          <div className="flex-1 flex flex-col min-h-0">
            <div className="flex items-center p-4 bg-secondary border-b border-gray-800 text-xs font-bold text-gray-500 uppercase tracking-widest gap-4">
              <div className="w-24">TIMESTAMP</div>
              <div className="w-32">ACTION</div>
              <div className="w-32">TARGET ID</div>
              <div className="flex-1">REASON</div>
              <div className="w-48 text-right">RESOLUTION</div>
            </div>
            <div className="flex-1 overflow-y-auto">
              {approvals.length === 0 ? (
                <div className="p-16 text-center text-gray-500 text-sm font-bold tracking-wider">NO PENDING APPROVALS</div>
              ) : (
                approvals.map((app) => (
                  <div key={app.id} className="flex items-center p-4 border-b border-gray-800 hover:bg-gray-800/50 transition-colors gap-4">
                    <div className="w-24 font-mono text-xs text-gray-500">{new Date(app.created_at * 1000).toLocaleTimeString()}</div>
                    <div className="w-32 font-mono text-xs text-warning">{app.action_type.toUpperCase()}</div>
                    <div className="w-32 font-mono text-xs text-white truncate">{app.target_identifier}</div>
                    <div className="flex-1 text-sm text-gray-300 truncate">{app.reason}</div>
                    <div className="w-48 text-right flex justify-end gap-2">
                      <button 
                        className="px-3 py-1 rounded-md text-xs font-bold bg-transparent text-danger hover:bg-danger/10 border border-transparent hover:border-danger/30 transition-colors"
                        onClick={() => handleResolve(app.id, 'rejected')}
                      >REJECT</button>
                      <button 
                        className="px-3 py-1 rounded-md text-xs font-bold bg-transparent text-accent hover:bg-accent/10 border border-transparent hover:border-accent/30 transition-colors"
                        onClick={() => handleResolve(app.id, 'approved')}
                      >APPROVE</button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

      </section>
    </div>
  );
};

export default HistoricalLogsPage;
