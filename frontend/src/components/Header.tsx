import React from 'react';
import type { AppTab } from '../hooks/useHashNavigation';
import type { SystemHealthResponse } from '../types/telemetry';

interface HeaderProps {
  activeTab: AppTab;
  onSelectTab: (tab: AppTab) => void;
  pendingHandoverCount: number;
  health: SystemHealthResponse | null;
  hasSessionKey: boolean;
  userEmail?: string;
  onLogout: () => void;
  onOpenAuthModal: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  activeTab,
  onSelectTab,
  pendingHandoverCount,
  health,
  hasSessionKey,
  userEmail,
  onLogout,
  onOpenAuthModal,
}) => {
  const statusKind =
    !health || health.status === 'offline'
      ? 'is-critical'
      : health.status === 'degraded'
        ? 'is-degraded'
        : '';

  const statusLabel =
    !health
      ? 'VERIFICANDO...'
      : health.status === 'offline'
        ? 'API OFFLINE'
        : health.status === 'degraded'
          ? 'MODO DEGRADADO'
          : 'UAZAPI · OPERANTE';

  return (
    <header className="institutional-header">
      <div className="prestige-beam" />
      <div className="header-inner">
        <div className="brand-cluster">
          <div className="brand-mark" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
              <path
                d="M4 17L10 11L14 15L20 7"
                stroke="#F8FAFC"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              <circle cx="20" cy="7" r="2.5" fill="#FF1E46" />
              <circle cx="4" cy="17" r="2.2" fill="#1E6BFF" />
            </svg>
          </div>
          <div>
            <div className="brand-wordmark">INTELIGENTTE // ECOSSISTEMA</div>
            <div className="brand-sub">AUTONOMOUS REVENUE &amp; CLOSER COMMAND</div>
          </div>
        </div>

        <nav className="nav-tabs" aria-label="Navegação Principal">
          <button
            type="button"
            className={`nav-tab-btn ${activeTab === 'overview' ? 'is-active' : ''}`}
            onClick={() => onSelectTab('overview')}
          >
            Visão Executiva
          </button>

          <button
            type="button"
            className={`nav-tab-btn ${activeTab === 'leads' ? 'is-active' : ''}`}
            onClick={() => onSelectTab('leads')}
          >
            <span>Carteira &amp; Dossiê</span>
            {pendingHandoverCount > 0 && (
              <span className="nav-tab-count" title="Leads aguardando Closer humano">
                {pendingHandoverCount}
              </span>
            )}
          </button>

          <button
            type="button"
            className={`nav-tab-btn ${activeTab === 'settings' ? 'is-active' : ''}`}
            onClick={() => onSelectTab('settings')}
          >
            Sala de Máquinas
          </button>
        </nav>

        <div className="telemetry-strip">
          {health?.ia_silenciada_global && (
            <span className="badge badge-closer" title="Kill-Switch global ativo">
              IA PAUSADA
            </span>
          )}

          <div
            className="status-pill"
            title={
              health?.alerta_operacional ??
              `Gateway: ${(health?.gateway_whatsapp ?? 'uazapi').toUpperCase()} | Buffers Redis: ${health?.buffers_pendentes ?? 0}`
            }
          >
            <span className={`status-dot ${statusKind}`} />
            <span>{statusLabel}</span>
            {health?.latency_ms !== undefined && (
              <span style={{ color: 'var(--text-dim)' }}>{health.latency_ms}ms</span>
            )}
          </div>

          {userEmail && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '12px', color: 'var(--text-muted, #94a3b8)', fontFamily: 'var(--font-mono)' }}>
                {userEmail}
              </span>
              <button
                type="button"
                className="btn btn-sm"
                onClick={onLogout}
                title="Encerrar sessão corporativa"
                style={{ color: '#FF6B8B', borderColor: 'rgba(255, 30, 70, 0.3)' }}
              >
                Sair
              </button>
            </div>
          )}

          {!userEmail && (
            <button
              type="button"
              className="btn btn-sm"
              onClick={onOpenAuthModal}
              title="Configurar chave administrativa da sessão (X-API-Key)"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="8" cy="15" r="4" />
                <path d="M10.85 12.15L19 4" />
                <path d="M18 5L20 7" />
                <path d="M15 8L17 10" />
              </svg>
              <span>{hasSessionKey ? 'Chave Ativa' : 'Chave API'}</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
};
