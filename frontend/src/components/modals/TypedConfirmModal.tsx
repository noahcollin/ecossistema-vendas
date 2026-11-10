import React, { useState } from 'react';

interface TypedConfirmModalProps {
  isOpen: boolean;
  title: string;
  description: string;
  confirmWord?: string;
  confirmButtonLabel: string;
  variant?: 'closer' | 'ai';
  isBusy?: boolean;
  onCancel: () => void;
  onConfirm: () => Promise<void> | void;
}

export const TypedConfirmModal: React.FC<TypedConfirmModalProps> = ({
  isOpen,
  title,
  description,
  confirmWord = 'CONFIRMAR',
  confirmButtonLabel,
  variant = 'closer',
  isBusy = false,
  onCancel,
  onConfirm,
}) => {
  const [typed, setTyped] = useState('');

  if (!isOpen) return null;

  const isMatched = typed.trim().toUpperCase() === confirmWord.toUpperCase();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isMatched || isBusy) return;
    await onConfirm();
    setTyped('');
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-card" style={{ maxWidth: '480px' }}>
        <div className="panel-header">
          <div>
            <div className={`eyebrow ${variant === 'closer' ? 'eyebrow-closer' : 'eyebrow-ai'}`}>
              CONFIRMAÇÃO DE GOVERNANÇA
            </div>
            <h2 className="section-title" style={{ marginTop: '4px' }}>
              {title}
            </h2>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <p style={{ color: 'var(--text-secondary)', fontSize: '13.5px' }}>{description}</p>

          <div>
            <label className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
              DIGITE &ldquo;{confirmWord}&rdquo; PARA PROSSEGUIR
            </label>
            <input
              type="text"
              className="field-input mono-metric"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              placeholder={confirmWord}
              autoFocus
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button
              type="button"
              className="btn"
              onClick={() => {
                setTyped('');
                onCancel();
              }}
              disabled={isBusy}
            >
              Cancelar
            </button>
            <button
              type="submit"
              className={`btn ${variant === 'closer' ? 'btn-closer' : 'btn-ai'}`}
              disabled={!isMatched || isBusy}
            >
              {isBusy ? 'Executando...' : confirmButtonLabel}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

