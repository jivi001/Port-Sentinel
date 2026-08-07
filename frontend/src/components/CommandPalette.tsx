import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, ShieldAlert, Activity, LayoutDashboard, Settings, History } from 'lucide-react';
import { useToast } from './ui/Toast';

interface CommandItem {
  id: string;
  name: string;
  icon: React.ReactNode;
  shortcut?: string;
  action: () => void;
}

export const CommandPalette: React.FC = () => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { toast } = useToast();

  const commands: CommandItem[] = [
    { id: 'dash', name: 'Dashboard', icon: <LayoutDashboard size={16} />, shortcut: '1', action: () => navigate('/') },
    { id: 'proc', name: 'Processes', icon: <Activity size={16} />, shortcut: '2', action: () => navigate('/processes') },
    { id: 'hist', name: 'History', icon: <History size={16} />, shortcut: '3', action: () => navigate('/history') },
    { id: 'threat', name: 'Threats Map', icon: <ShieldAlert size={16} />, shortcut: '4', action: () => navigate('/threats') },
    { id: 'set', name: 'Settings', icon: <Settings size={16} />, shortcut: '5', action: () => navigate('/settings') },
    { id: 'block', name: 'Emergency Block All', icon: <ShieldAlert size={16} color="red" />, action: () => toast({ title: 'Lockdown Initiated', description: 'Blocking all non-essential outbound traffic.', variant: 'critical' }) },
  ];

  const filteredCommands = commands.filter((c) =>
    c.name.toLowerCase().includes(query.toLowerCase())
  );

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        setOpen((open) => !open);
      }
      
      if (!open) {
        // Global number shortcuts when palette is closed
        if (e.metaKey || e.ctrlKey) return;
        
        const num = parseInt(e.key);
        if (num >= 1 && num <= 5) {
          const cmd = commands.find(c => c.shortcut === e.key);
          if (cmd) {
            e.preventDefault();
            cmd.action();
          }
        }
      }
    };

    document.addEventListener('keydown', down);
    return () => document.removeEventListener('keydown', down);
  }, [open, navigate, commands]);

  useEffect(() => {
    if (open) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 10);
    }
  }, [open]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % filteredCommands.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filteredCommands.length) % filteredCommands.length);
    } else if (e.key === 'Enter' && filteredCommands[selectedIndex]) {
      e.preventDefault();
      filteredCommands[selectedIndex].action();
      setOpen(false);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  if (!open) return null;

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 10000,
      backgroundColor: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'flex-start', justifyContent: 'center',
      paddingTop: '10vh'
    }} onClick={() => setOpen(false)}>
      <div 
        className="widget-card"
        style={{ width: '100%', maxWidth: '600px', overflow: 'hidden' }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ display: 'flex', alignItems: 'center', padding: '16px', borderBottom: '1px solid var(--border-dim)' }}>
          <Search size={20} color="var(--text-muted)" style={{ marginRight: '12px' }} />
          <input
            ref={inputRef}
            type="text"
            placeholder="Type a command or search..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            style={{
              width: '100%', background: 'transparent', border: 'none',
              color: 'var(--text-primary)', fontSize: '1.1rem', outline: 'none'
            }}
          />
        </div>
        <div style={{ maxHeight: '400px', overflowY: 'auto', padding: '8px' }}>
          {filteredCommands.length === 0 ? (
            <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)' }}>
              No commands found.
            </div>
          ) : (
            filteredCommands.map((cmd, idx) => (
              <div
                key={cmd.id}
                onMouseEnter={() => setSelectedIndex(idx)}
                onClick={() => {
                  cmd.action();
                  setOpen(false);
                }}
                style={{
                  display: 'flex', alignItems: 'center', padding: '12px 16px',
                  borderRadius: 'var(--radius-md)', cursor: 'pointer',
                  backgroundColor: idx === selectedIndex ? 'var(--bg-active)' : 'transparent',
                  color: idx === selectedIndex ? 'var(--text-primary)' : 'var(--text-secondary)'
                }}
              >
                <div style={{ marginRight: '12px', color: idx === selectedIndex ? 'var(--accent-blue)' : 'currentColor' }}>
                  {cmd.icon}
                </div>
                <span style={{ flex: 1, fontWeight: idx === selectedIndex ? 600 : 400 }}>{cmd.name}</span>
                {cmd.shortcut && (
                  <span style={{
                    fontSize: '0.7rem', padding: '2px 6px', borderRadius: '4px',
                    backgroundColor: 'var(--bg-surface)', border: '1px solid var(--border-dim)'
                  }}>
                    {cmd.shortcut}
                  </span>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
