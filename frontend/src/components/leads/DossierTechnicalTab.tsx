import React from 'react';
import type { Lead } from '../../types/telemetry';
import { formatDateTimeBR, getCanalLabel } from '../../utils/formatters';

interface DossierTechnicalTabProps {
  lead: Lead;
  isBusy: boolean;
  onRequestResetMemory: () => void;
  onRequestDeleteLead: () => void;
}

export const DossierTechnicalTab: React.FC<DossierTechnicalTabProps> = ({
  lead,
  isBusy,
  onRequestResetMemory,
  onRequestDeleteLead,
}) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '12px',
        }}
      >
        <div className="surface-panel" style={{ padding: '14px 16px' }}>
          <div className="eyebrow">ID INTERNO &amp; CADASTRO</div>
          <div className="mono-metric" style={{ fontWeight: 600, marginTop: '4px' }}>
            #{lead.id} · {formatDateTimeBR(lead.criado_em)}
          </div>
        </div>

        <div className="surface-panel" style={{ padding: '14px 16px' }}>
          <div className="eyebrow">ENTRADA &amp; CANAL</div>
          <div style={{ fontWeight: 600, marginTop: '4px' }}>
            {lead.tipo_entrada} · {getCanalLabel(lead.origem_canal)}
          </div>
        </div>

        <div className="surface-panel" style={{ padding: '14px 16px' }}>
          <div className="eyebrow">CONSENTIMENTO LGPD</div>
          <div style={{ fontWeight: 600, marginTop: '4px' }}>
            {lead.opt_out ? (
              <span className="badge badge-closer">OPT-OUT ATIVO</span>
            ) : (
              <span className="badge badge-won">ATIVO / PERMITIDO</span>
            )}
          </div>
        </div>
      </div>

      <div className="surface-panel" style={{ padding: '16px' }}>
        <div className="eyebrow" style={{ marginBottom: '10px' }}>
          TAGS COGNITIVAS &amp; OPERACIONAIS SINCRONIZADAS
        </div>
        {lead.tags.length === 0 ? (
          <span style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
            Nenhuma tag aplicada a este lead.
          </span>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {lead.tags.map((tag) => (
              <span key={tag} className="badge">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      <div
        className="surface-panel"
        style={{
          padding: '18px',
          borderColor: 'var(--red-closer-border)',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
        }}
      >
        <div>
          <div className="eyebrow eyebrow-closer">ZONA DE MANUTENÇÃO DO REGISTRO</div>
          <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '4px' }}>
            Use o reset de memória para reiniciar testes de conversação mantendo o telefone cadastrado, ou exclua permanentemente o lead e seu histórico em cascata.
          </p>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
          <button
            type="button"
            className="btn btn-sm"
            onClick={onRequestResetMemory}
            disabled={isBusy}
          >
            Reiniciar Memória &amp; Conversa
          </button>

          <button
            type="button"
            className="btn btn-sm btn-outline-closer"
            onClick={onRequestDeleteLead}
            disabled={isBusy}
          >
            Excluir Lead Permanentemente
          </button>
        </div>
      </div>
    </div>
  );
};

