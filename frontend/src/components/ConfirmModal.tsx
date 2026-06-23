/**
 * Sentinel — ConfirmModal Component
 *
 * Reusable confirmation dialog for destructive actions (kill, block, etc.).
 * Glassmorphism-themed overlay with cancel/confirm buttons.
 */

import React from 'react';

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'warning' | 'default';
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmModal: React.FC<ConfirmModalProps> = ({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  onConfirm,
  onCancel,
}) => {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm transition-opacity" onClick={onCancel}>
      <div className="bg-surface border border-gray-800 rounded-xl shadow-2xl max-w-md w-full m-4 p-6 flex flex-col gap-4 transform transition-transform scale-100" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3">
          <span className="text-2xl">
            {variant === 'danger' ? '⚠️' : variant === 'warning' ? '⚡' : 'ℹ️'}
          </span>
          <h3 className="text-lg font-bold text-white tracking-wide">{title}</h3>
        </div>
        <p className="text-gray-400 text-sm leading-relaxed">{message}</p>
        <div className="flex justify-end gap-3 mt-4">
          <button 
            className="px-4 py-2 rounded-lg font-bold text-xs bg-transparent text-gray-400 hover:bg-white/5 border border-transparent transition-colors" 
            onClick={onCancel}
          >
            {cancelLabel}
          </button>
          <button 
            className={`px-4 py-2 rounded-lg font-bold text-xs border border-transparent transition-colors ${
              variant === 'danger' 
                ? 'bg-danger/10 text-danger hover:bg-danger/20 border-danger/30' 
                : variant === 'warning' 
                  ? 'bg-warning/10 text-warning hover:bg-warning/20 border-warning/30' 
                  : 'bg-primary/10 text-primary hover:bg-primary/20 border-primary/30'
            }`} 
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmModal;
