import React from 'react';

interface ConfirmModalProps {
  open: boolean;
  title: string;
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

const ConfirmModal: React.FC<ConfirmModalProps> = ({ open, title, message, onConfirm, onCancel }) => {
  if (!open) return null;

  return (
    <div style={{
      position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh',
      backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', 
      justifyContent: 'center', zIndex: 1000
    }}>
      <div style={{
        backgroundColor: 'var(--bg-card, #1e1e2e)', padding: '2rem', borderRadius: '8px', 
        minWidth: '400px', boxShadow: '0 4px 6px rgba(0,0,0,0.3)', border: '1px solid var(--border-color, #333)'
      }}>
        <h2 style={{ marginTop: 0, color: 'var(--text-main, #fff)' }}>{title}</h2>
        <p style={{ color: 'var(--text-muted, #ccc)', marginBottom: '2rem' }}>{message}</p>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '1rem' }}>
          <button onClick={onCancel} style={{ 
            padding: '0.5rem 1rem', borderRadius: '4px', border: '1px solid var(--border-color, #555)', 
            backgroundColor: 'transparent', color: 'var(--text-main, #fff)', cursor: 'pointer' 
          }}>
            Cancel
          </button>
          <button onClick={onConfirm} style={{ 
            padding: '0.5rem 1rem', borderRadius: '4px', border: 'none', 
            backgroundColor: 'var(--accent-red, #ff4d4d)', color: 'white', cursor: 'pointer' 
          }}>
            Confirm
          </button>
        </div>
      </div>
    </div>
  );
};

export default ConfirmModal;
