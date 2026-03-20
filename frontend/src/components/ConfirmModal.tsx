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
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-card__header">
          <span className="modal-card__icon">
            {variant === 'danger' ? '⚠️' : variant === 'warning' ? '⚡' : 'ℹ️'}
          </span>
          <h3 className="modal-card__title">{title}</h3>
        </div>
        <p className="modal-card__message">{message}</p>
        <div className="modal-card__actions">
          <button className="btn btn--ghost" onClick={onCancel}>
            {cancelLabel}
          </button>
          <button className={`btn btn--${variant}`} onClick={onConfirm}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmModal;
