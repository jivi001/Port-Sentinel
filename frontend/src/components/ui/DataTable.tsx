import React, { useState, useMemo } from 'react';
import { Search, ChevronUp, ChevronDown, MoreVertical } from 'lucide-react';
import clsx from 'clsx';

export interface ColumnDef<T> {
  key: Extract<keyof T, string>;
  header: string;
  render?: (item: T) => React.ReactNode;
  sortable?: boolean;
  width?: string;
}

export interface DataTableProps<T> {
  data: T[];
  columns: ColumnDef<T>[];
  keyExtractor: (item: T) => string;
  onRowClick?: (item: T) => void;
  contextMenuActions?: { label: string; onClick: (item: T) => void; variant?: 'danger' | 'default' }[];
  searchable?: boolean;
  searchPlaceholder?: string;
  searchFilter?: (item: T, query: string) => boolean;
  emptyMessage?: string;
}

export function DataTable<T>({
  data,
  columns,
  keyExtractor,
  onRowClick,
  contextMenuActions,
  searchable = true,
  searchPlaceholder = 'Search...',
  searchFilter,
  emptyMessage = 'No data found.',
}: DataTableProps<T>) {
  const [query, setQuery] = useState('');
  const [sortKey, setSortKey] = useState<Extract<keyof T, string> | null>(null);
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [contextMenuOpenId, setContextMenuOpenId] = useState<string | null>(null);

  const handleSort = (key: Extract<keyof T, string>) => {
    if (sortKey === key) {
      if (sortDir === 'asc') setSortDir('desc');
      else setSortKey(null);
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };

  const filteredData = useMemo(() => {
    let result = [...data];
    if (query && searchFilter) {
      result = result.filter(item => searchFilter(item, query));
    }
    
    if (sortKey) {
      result.sort((a, b) => {
        const valA = a[sortKey];
        const valB = b[sortKey];
        if (valA < valB) return sortDir === 'asc' ? -1 : 1;
        if (valA > valB) return sortDir === 'asc' ? 1 : -1;
        return 0;
      });
    }
    return result;
  }, [data, query, sortKey, sortDir, searchFilter]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {searchable && (
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-dim)', display: 'flex', alignItems: 'center' }}>
          <Search size={16} color="var(--text-muted)" style={{ marginRight: '8px' }} />
          <input
            type="text"
            placeholder={searchPlaceholder}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ border: 'none', background: 'transparent', color: 'var(--text-primary)', outline: 'none', width: '100%', fontSize: '0.85rem' }}
          />
        </div>
      )}
      
      <div style={{ display: 'flex', padding: '12px 16px', background: 'var(--table-header-bg)', borderBottom: '1px solid var(--border-dim)' }}>
        {columns.map(col => (
          <div
            key={col.key}
            onClick={() => col.sortable !== false && handleSort(col.key)}
            style={{ 
              width: col.width || 'flex-1', flex: col.width ? 'none' : 1,
              cursor: col.sortable !== false ? 'pointer' : 'default',
              display: 'flex', alignItems: 'center', fontSize: '0.7rem', fontWeight: 700, 
              color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em'
            }}
          >
            {col.header}
            {sortKey === col.key && (
              sortDir === 'asc' ? <ChevronUp size={14} style={{ marginLeft: '4px' }} /> : <ChevronDown size={14} style={{ marginLeft: '4px' }} />
            )}
          </div>
        ))}
        {contextMenuActions && <div style={{ width: '40px' }} />}
      </div>

      <div style={{ flex: 1, overflowY: 'auto' }}>
        {filteredData.length === 0 ? (
          <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
            {emptyMessage}
          </div>
        ) : (
          filteredData.map(item => {
            const rowId = keyExtractor(item);
            return (
              <div
                key={rowId}
                className="data-row"
                onClick={() => onRowClick?.(item)}
                style={{ cursor: onRowClick ? 'pointer' : 'default', position: 'relative' }}
              >
                {columns.map(col => (
                  <div key={col.key} style={{ width: col.width || 'flex-1', flex: col.width ? 'none' : 1 }}>
                    {col.render ? col.render(item) : String(item[col.key] || '')}
                  </div>
                ))}
                
                {contextMenuActions && (
                  <div style={{ width: '40px', display: 'flex', justifyContent: 'flex-end', position: 'relative' }}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setContextMenuOpenId(contextMenuOpenId === rowId ? null : rowId);
                      }}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
                    >
                      <MoreVertical size={16} />
                    </button>
                    
                    {contextMenuOpenId === rowId && (
                      <div 
                        style={{
                          position: 'absolute', top: '100%', right: '10px', zIndex: 100,
                          background: 'var(--bg-secondary)', border: '1px solid var(--border-dim)',
                          borderRadius: 'var(--radius-md)', boxShadow: 'var(--shadow-md)',
                          minWidth: '150px', padding: '4px 0', overflow: 'hidden'
                        }}
                      >
                        {contextMenuActions.map((action, idx) => (
                          <div
                            key={idx}
                            onClick={(e) => {
                              e.stopPropagation();
                              setContextMenuOpenId(null);
                              action.onClick(item);
                            }}
                            className={clsx('context-menu-item', { 'context-menu-item--danger': action.variant === 'danger' })}
                            style={{
                              padding: '8px 16px', fontSize: '0.8rem', cursor: 'pointer',
                              color: action.variant === 'danger' ? 'var(--accent-red)' : 'var(--text-primary)'
                            }}
                          >
                            {action.label}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
      {/* Click outside to close context menu */}
      {contextMenuOpenId && (
        <div 
          onClick={() => setContextMenuOpenId(null)}
          style={{ position: 'fixed', inset: 0, zIndex: 99 }} 
        />
      )}
    </div>
  );
}
