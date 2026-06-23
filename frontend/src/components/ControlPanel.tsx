/**
 * Sentinel — Professional Search Control
 */

import React, { useState, useEffect } from 'react';

interface ControlPanelProps {
  filter: string;
  onFilterChange: (value: string) => void;
}

const ControlPanel: React.FC<ControlPanelProps> = ({ filter, onFilterChange }) => {
  const [localFilter, setLocalFilter] = useState(filter);

  useEffect(() => {
    if (filter !== localFilter) {
      setLocalFilter(filter);
    }
  }, [filter]);

  useEffect(() => {
    const handler = window.setTimeout(() => {
      onFilterChange(localFilter);
    }, 250);
    return () => clearTimeout(handler);
  }, [localFilter, onFilterChange]);

  return (
    <div className="flex items-center gap-3 flex-1 max-w-[400px]">
      <input
        type="text"
        placeholder="SEARCH ACTIVE NODES..."
        value={localFilter}
        onChange={(e) => setLocalFilter(e.target.value)}
        autoComplete="off"
        spellCheck={false}
        className="w-full bg-secondary border border-border-main rounded-md px-4 py-2 text-text-main text-[0.7rem] font-bold tracking-widest outline-none focus:border-primary transition-colors placeholder-text-dim"
      />
    </div>
  );
};

export default React.memo(ControlPanel);
