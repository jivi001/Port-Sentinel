import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { Badge } from './Badge';
import { X } from 'lucide-react';
import clsx from 'clsx';

export type ToastVariant = 'info' | 'success' | 'critical' | 'default';

export interface ToastMessage {
  id: string;
  title: string;
  description?: string;
  variant?: ToastVariant;
}

interface ToastContextType {
  toast: (message: Omit<ToastMessage, 'id'>) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const toast = useCallback((message: Omit<ToastMessage, 'id'>) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { ...message, id }]);

    // Auto dismiss after 5s
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 5000);
  }, []);

  const dismiss = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div style={{
        position: 'fixed',
        bottom: '24px',
        right: '24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
        zIndex: 9999,
      }}>
        {toasts.map((t) => (
          <div
            key={t.id}
            className={clsx(
              'widget-card',
              {
                'border-red-500': t.variant === 'critical',
                'border-blue-500': t.variant === 'info',
                'border-green-500': t.variant === 'success',
              }
            )}
            style={{
              padding: '16px',
              minWidth: '300px',
              maxWidth: '400px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              animation: 'slideIn 0.3s ease-out forwards',
              backgroundColor: 'var(--bg-glass)',
            }}
          >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                {t.variant && <Badge variant={t.variant}>{t.variant.toUpperCase()}</Badge>}
                <strong style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>{t.title}</strong>
              </div>
              {t.description && (
                <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{t.description}</span>
              )}
            </div>
            <button
              onClick={() => dismiss(t.id)}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};
