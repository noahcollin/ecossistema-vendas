import React from 'react';
import type { Lead } from '../../types/telemetry';
import {
  formatCurrencyBRL,
  getControleLabel,
  getEtapaLabel,
  getTemperaturaLabel,
} from '../../utils/formatters';

interface LeadsListColumnProps {
  leads: Lead[];
  activeLeadId: number | null;
  isLoading: boolean;
  onSelectLead: (lead: Lead) => void;
}

export const LeadsListColumn: React.FC<LeadsListColumnProps> = ({
  leads,
  activeLeadId,
  isLoading,
  onSelectLead,
}) => {
  return (
    <aside className="leads-list-panel" aria-label="Lista de Leads">
      <div className="panel-header" style={{ padding: '14px 16px' }}>
        <span className="eyebrow">FILA OPERACIONAL DE NEGÓCIOS</span>
        <span className="mono-metric" style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
          {leads.length} item(ns)
        </span>
      </div>

      <div className="leads-list-scroll">
        {isLoading && leads.length === 0 ? (
          <div style={{ padding: '28px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Carregando carteira...
          </div>
        ) : leads.length === 0 ? (
          <div style={{ padding: '28px 16px', textAlign: 'center', color: 'var(--text-muted)' }}>
            Nenhum lead corresponde aos filtros selecionados.
          </div>
        ) : (
          leads.map((lead) => {
            const isSelected = lead.id === activeLeadId;
            const isHandover = lead.controle === 'TRANSBORDO_SOLICITADO';

            const tempClass =
              lead.temperatura === 'QUENTE'
                ? 'badge-closer'
                : lead.temperatura === 'MORNO'
                  ? 'badge-warm'
                  : 'badge-muted';

            const ctrlClass =
              lead.controle === 'TRANSBORDO_SOLICITADO'
                ? 'badge-closer'
                : lead.controle === 'HUMANO_ASSUMIU'
                  ? 'badge-warm'
                  : 'badge-ai';

            return (
              <button
                key={lead.id}
                type="button"
                className={`lead-row-item ${isSelected ? 'is-selected' : ''} ${
                  isHandover ? 'is-handover' : ''
                }`}
                onClick={() => onSelectLead(lead)}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', width: '100%' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '13.5px', color: 'var(--text-primary)' }}>
                      {lead.nome?.trim() || 'Contato sem nome'}
                    </div>
                    <div className="mono-metric" style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                      {lead.telefone}
                    </div>
                  </div>

                  <span className="mono-metric" style={{ fontSize: '12px', fontWeight: 600 }}>
                    {formatCurrencyBRL(lead.valor_estimado)}
                  </span>
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  <span className="badge">{getEtapaLabel(lead.etapa_funil)}</span>
                  <span className={`badge ${tempClass}`}>
                    {getTemperaturaLabel(lead.temperatura)}
                  </span>
                  <span className={`badge ${ctrlClass}`}>
                    {getControleLabel(lead.controle)}
                  </span>
                </div>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
};
