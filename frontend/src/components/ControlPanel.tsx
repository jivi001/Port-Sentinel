/**
 * Sentinel — Professional Search Control
 */

import React from 'react';

interface ControlPanelProps {
  filter: string;
  onFilterChange: (value: string) => void;
}

const ControlPanel: React.FC<ControlPanelProps> = ({ filter, onFilterChange }) => {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, maxWidth: '400px' }}>
      <input
        type="text"
        placeholder="SEARCH ACTIVE NODES..."
        value={filter}
        onChange={(e) => onFilterChange(e.target.value)}
        autoComplete="off"
        spellCheck={false}
        style={{
          width: '100%',
          background: 'var(--bg-glass)',
          border: '1px solid var(--border-default)',
          borderRadius: '6px',
          padding: '8px 16px',
          color: 'white',
          fontSize: '0.7rem',
          fontWeight: 700,
          letterSpacing: '0.05em',
          outline: 'none',
        }}
      />
    </div>
  );
};

export default React.memo(ControlPanel);
