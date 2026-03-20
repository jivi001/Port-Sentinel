/**
 * Sentinel — ControlPanel Component
 *
 * Search/filter bar sitting above the port table.
 */

import React from 'react';

interface ControlPanelProps {
  filter: string;
  onFilterChange: (value: string) => void;
  portCount: number;
}

const ControlPanel: React.FC<ControlPanelProps> = ({ filter, onFilterChange, portCount }) => {
  return (
    <div className="control-panel" id="control-panel">
      <input
        id="port-filter"
        className="control-panel__search"
        type="text"
        placeholder="Filter by port, app name, PID, or protocol…"
        value={filter}
        onChange={(e) => onFilterChange(e.target.value)}
        autoComplete="off"
        spellCheck={false}
      />
      <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
        {portCount} port{portCount !== 1 ? 's' : ''}
      </span>
    </div>
  );
};

export default React.memo(ControlPanel);
