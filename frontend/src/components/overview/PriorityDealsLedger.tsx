import React from 'react';
import type { Lead } from '../../types/telemetry';
import {
  formatCurrencyBRL,
  formatDateTimeBR,
  getCanalLabel,
  getControleLabel,
  getEtapaLabel,
  getTemperaturaLabel,
} from '../../utils/formatters';

interface PriorityDealsLedgerProps {
  deals: Lead[];
  onOpenLead: (leadId: number) => void;
  onOpenAllLeads: () => void;
}

export const PriorityDealsLedger: React.FC<PriorityDealsLedgerProps> = ({
  deals,
  onOpenLead,
  onOpenAllLeads,
}) => {
  return (
    <section className="surface-panel" aria-label="Negociações Prioritárias">
      <div className="panel-header">
        <div>
          <div className="eyebrow">MESA DE COMANDO COMERCIAL</div>
          <h2 className="section-title" style={{ marginTop: '2px' }}>
            Negociações Prioritárias (Clique para abrir o Dossiê)
          </h2>
        </div>

        <button type="button" className="btn btn-sm" onClick={onOpenAllLeads}>
          Ver Carteira Completa
        </button>
      </div>

      {deals.length === 0 ? (
        <div className="panel-body" style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '36px' }}>
          Nenhuma negociação ativa encontrada. Assim que novos leads entrarem via WhatsApp (Uazapi), aparecerão automaticamente aqui.
        </div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="ledger-table">
            <thead>
              <tr>
                <th>Lead / Contato</th>
                <th>Canal</th>
                <th>Estágio</th>
                <th>Temperatura</th>
                <th>Condução</th>
                <th>Valor Estimado</th>
                <th>Entrada</th>
              </tr>
            </thead>
            <tbody>
              {deals.map((lead) => {
                const tempBadge =
                  lead.temperatura === 'QUENTE'
                    ? 'badge-closer'
                    : lead.temperatura === 'MORNO'
                      ? 'badge-warm'
                      : 'badge-muted';

                const ctrlBadge =
                  lead.controle === 'TRANSBORDO_SOLICITADO'
                    ? 'badge-closer'
                    : lead.controle === 'HUMANO_ASSUMIU'
                      ? 'badge-warm'
                      : 'badge-ai';

                return (
                  <tr
                    key={lead.id}
                    className="is-clickable"
                    onClick={() => onOpenLead(lead.id)}
                    title="Abrir Dossiê Executivo e Conversa WhatsApp deste lead"
                  >
                    <td>
                      <div style={{ fontWeight: 600 }}>{lead.nome || 'Contato sem nome'}</div>
                      <div className="mono-metric" style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                        {lead.telefone}
                      </div>
                    </td>
                    <td style={{ color: 'var(--text-secondary)' }}>{getCanalLabel(lead.origem_canal)}</td>
                    <td>
                      <span className="badge">{getEtapaLabel(lead.etapa_funil)}</span>
                    </td>
                    <td>
                      <span className={`badge ${tempBadge}`}>
                        {getTemperaturaLabel(lead.temperatura)}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${ctrlBadge}`}>
                        {getControleLabel(lead.controle)}
                      </span>
                    </td>
                    <td className="mono-metric" style={{ fontWeight: 600 }}>
                      {formatCurrencyBRL(lead.valor_estimado)}
                    </td>
                    <td className="mono-metric" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      {formatDateTimeBR(lead.criado_em)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
};

