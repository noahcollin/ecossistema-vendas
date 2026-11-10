import React from 'react';
import type { SystemHealthResponse } from '../../types/telemetry';

interface InfrastructureHealthSectionProps {
  health: SystemHealthResponse | null;
  onRefreshHealth: () => void;
}

export const InfrastructureHealthSection: React.FC<InfrastructureHealthSectionProps> = ({
  health,
  onRefreshHealth,
}) => {
  const comp = health?.componentes ?? {};
  const pgOk = comp.postgres === 'conectado';
  const redisOk = comp.redis === 'conectado';
  const uazapiOk = Boolean(comp.uazapi_token);
  const openaiOk = Boolean(comp.openai_key) && comp.openai_creditos !== 'esgotado';

  return (
    <section className="surface-panel">
      <div className="panel-header">
        <div>
          <div className="eyebrow">TELEMETRIA REAL DE INFRAESTRUTURA (/HEALTH)</div>
          <h2 className="section-title" style={{ marginTop: '2px' }}>
            Conectividade dos Motores &amp; Credenciais
          </h2>
        </div>
        <button type="button" className="btn btn-sm" onClick={onRefreshHealth}>
          Testar Conectividade
        </button>
      </div>

      <div
        className="panel-body"
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))',
          gap: '12px',
        }}
      >
        <div className="surface-elevated" style={{ padding: '14px 16px' }}>
          <div className="eyebrow">POSTGRESQL 15 (ASYNC)</div>
          <div style={{ marginTop: '8px' }}>
            <span className={`badge ${pgOk ? 'badge-won' : 'badge-closer'}`}>
              {comp.postgres ? comp.postgres.toUpperCase() : 'INDISPONÍVEL'}
            </span>
          </div>
        </div>

        <div className="surface-elevated" style={{ padding: '14px 16px' }}>
          <div className="eyebrow">REDIS CACHE &amp; DEBOUNCE</div>
          <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span className={`badge ${redisOk ? 'badge-won' : 'badge-closer'}`}>
              {comp.redis ? comp.redis.toUpperCase() : 'INDISPONÍVEL'}
            </span>
            <span className="mono-metric" style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
              {health?.buffers_pendentes ?? 0} buffer(s)
            </span>
          </div>
        </div>

        <div className="surface-elevated" style={{ padding: '14px 16px' }}>
          <div className="eyebrow">GATEWAY WHATSAPP (UAZAPI)</div>
          <div style={{ marginTop: '8px' }}>
            <span className={`badge ${uazapiOk ? 'badge-won' : 'badge-warm'}`}>
              {uazapiOk ? 'TOKEN CONFIGURADO' : 'TOKEN AUSENTE'}
            </span>
          </div>
        </div>

        <div className="surface-elevated" style={{ padding: '14px 16px' }}>
          <div className="eyebrow">OPENAI (GPT-4O / MINI)</div>
          <div style={{ marginTop: '8px' }}>
            <span className={`badge ${openaiOk ? 'badge-won' : 'badge-closer'}`}>
              {comp.openai_creditos === 'esgotado'
                ? 'COTA ESGOTADA'
                : comp.openai_key
                  ? 'OPERANTE'
                  : 'CHAVE AUSENTE'}
            </span>
          </div>
        </div>
      </div>
    </section>
  );
};

