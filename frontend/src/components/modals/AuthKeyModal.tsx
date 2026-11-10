import React, { useState } from 'react';
import { clearStoredApiKey, getStoredApiKey, setStoredApiKey } from '../../services/api';

interface AuthKeyModalProps {
  isOpen: boolean;
  wasUnauthorized: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export const AuthKeyModal: React.FC<AuthKeyModalProps> = ({
  isOpen,
  wasUnauthorized,
  onClose,
  onSaved,
}) => {
  const [apiKeyInput, setApiKeyInput] = useState<string>(() => getStoredApiKey());

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setStoredApiKey(apiKeyInput);
    onSaved();
    onClose();
  };

  const handleClear = () => {
    clearStoredApiKey();
    setApiKeyInput('');
    onSaved();
    onClose();
  };

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="auth-modal-title">
      <div className="modal-card" style={{ maxWidth: '480px' }}>
        <div className="prestige-beam" />
        <div className="panel-header">
          <div>
            <div className="eyebrow eyebrow-ai">SEGURANÇA DE SESSÃO</div>
            <h2 id="auth-modal-title" className="section-title" style={{ marginTop: '4px' }}>
              Credencial Administrativa (X-API-Key)
            </h2>
          </div>
          <button type="button" className="btn btn-sm btn-ghost" onClick={onClose}>
            Fechar
          </button>
        </div>

        <form onSubmit={handleSubmit} className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {wasUnauthorized && (
            <div className="alert-banner is-error" style={{ marginBottom: 0 }}>
              <span>
                O servidor exigiu autenticação (`HTTP 401`). Informe a `ADMIN_API_KEY` configurada no `.env` do backend.
              </span>
            </div>
          )}

          <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
            A chave fica armazenada apenas no `sessionStorage` desta aba e nunca é exposta no bundle público da aplicação.
          </p>

          <div>
            <label htmlFor="admin-api-key-input" className="eyebrow" style={{ display: 'block', marginBottom: '6px' }}>
              CHAVE DE ADMINISTRAÇÃO
            </label>
            <input
              id="admin-api-key-input"
              type="password"
              className="field-input mono-metric"
              placeholder="Insira sua ADMIN_API_KEY..."
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              autoFocus
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', marginTop: '6px' }}>
            <button type="button" className="btn btn-ghost" onClick={handleClear}>
              Limpar Sessão
            </button>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button type="button" className="btn" onClick={onClose}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-ai">
                Autenticar Sessão
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

