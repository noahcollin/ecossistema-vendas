import React from 'react';
import { mapLeadToQualificationViewModel } from '../../mappers/leadMapper';
import type { Lead } from '../../types/telemetry';
import {
  formatCurrencyBRL,
  formatDateTimeBR,
  getControleLabel,
  getDesfechoLabel,
  getEtapaLabel,
  getTemperaturaLabel,
} from '../../utils/formatters';

interface BriefingModalProps {
  isOpen: boolean;
  mode: 'single' | 'batch';
  lead: Lead | null;
  leads: Lead[];
  onClose: () => void;
}

export const BriefingModal: React.FC<BriefingModalProps> = ({
  isOpen,
  mode,
  lead,
  leads,
  onClose,
}) => {
  if (!isOpen) return null;
  if (mode === 'single' && !lead) return null;

  const totalPipeline = leads
    .filter((l) => l.desfecho === 'EM_ANDAMENTO')
    .reduce((acc, l) => acc + (l.valor_estimado ?? 0), 0);

  const totalWon = leads
    .filter((l) => l.desfecho === 'GANHO')
    .reduce((acc, l) => acc + (l.valor_estimado ?? 0), 0);

  const hotLeads = leads.filter((l) => l.temperatura === 'QUENTE' || l.controle === 'TRANSBORDO_SOLICITADO');
  const singleVm = lead ? mapLeadToQualificationViewModel(lead) : null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true">
      <div className="modal-card" style={{ maxWidth: '760px' }}>
        <div className="prestige-beam" />
        <div className="panel-header">
          <div>
            <div className="eyebrow eyebrow-ai">
              {mode === 'single' ? 'DOSSIÊ COMERCIAL INDIVIDUAL' : 'BRIEFING EXECUTIVO DE CARTEIRA'}
            </div>
            <h2 className="section-title" style={{ marginTop: '4px' }}>
              {mode === 'single' && singleVm
                ? `${singleVm.displayName} (${lead?.telefone})`
                : `Relatório Consolidado — ${leads.length} Oportunidade(s)`}
            </h2>
          </div>

          <div className="no-print" style={{ display: 'flex', gap: '8px' }}>
            <button type="button" className="btn btn-sm btn-ai" onClick={() => window.print()}>
              Imprimir / Exportar PDF
            </button>
            <button type="button" className="btn btn-sm" onClick={onClose}>
              Fechar
            </button>
          </div>
        </div>

        <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {mode === 'single' && lead && singleVm ? (
            <>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                  gap: '12px',
                }}
              >
                <div className="surface-elevated" style={{ padding: '12px 14px' }}>
                  <div className="eyebrow">ETAPA &amp; DESFECHO</div>
                  <div style={{ fontWeight: 700, marginTop: '4px' }}>
                    {getEtapaLabel(lead.etapa_funil)} · {getDesfechoLabel(lead.desfecho)}
                  </div>
                </div>
                <div className="surface-elevated" style={{ padding: '12px 14px' }}>
                  <div className="eyebrow">VALOR ESTIMADO</div>
                  <div className="mono-metric" style={{ fontWeight: 700, marginTop: '4px', fontSize: '15px' }}>
                    {singleVm.valorEstimadoFormatado}
                  </div>
                </div>
                <div className="surface-elevated" style={{ padding: '12px 14px' }}>
                  <div className="eyebrow">CONTROLE &amp; TEMPERATURA</div>
                  <div style={{ fontWeight: 700, marginTop: '4px' }}>
                    {getControleLabel(lead.controle)} · {getTemperaturaLabel(lead.temperatura)}
                  </div>
                </div>
              </div>

              <div className="surface-panel" style={{ padding: '16px' }}>
                <div className="eyebrow" style={{ marginBottom: '6px' }}>
                  SÍNTESE EXECUTIVA &amp; HISTÓRIA DO NEGÓCIO
                </div>
                <p style={{ color: 'var(--text-secondary)', fontSize: '13.5px' }}>
                  {singleVm.resumoExecutivo}
                </p>
              </div>

              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
                  gap: '12px',
                }}
              >
                <div className="surface-panel" style={{ padding: '14px' }}>
                  <div className="eyebrow">SEGMENTO &amp; EQUIPE</div>
                  <div style={{ marginTop: '4px', fontWeight: 600 }}>
                    {singleVm.segmento} · Equipe: {singleVm.tamanhoEquipe}
                  </div>
                </div>
                <div className="surface-panel" style={{ padding: '14px' }}>
                  <div className="eyebrow">SOLUÇÃO DE INTERESSE</div>
                  <div style={{ marginTop: '4px', fontWeight: 600 }}>{singleVm.solucaoInteresse}</div>
                </div>
                <div className="surface-panel" style={{ padding: '14px' }}>
                  <div className="eyebrow">GARGALO PRINCIPAL</div>
                  <div style={{ marginTop: '4px', fontWeight: 600 }}>{singleVm.gargaloPrincipal}</div>
                </div>
                <div className="surface-panel" style={{ padding: '14px' }}>
                  <div className="eyebrow">DECISOR &amp; PRAZO</div>
                  <div style={{ marginTop: '4px', fontWeight: 600 }}>
                    {singleVm.decisorLabel} · {singleVm.prazoImplementacao}
                  </div>
                </div>
              </div>

              {lead.dossie_comercial?.proximo_passo && (
                <div className="surface-elevated" style={{ padding: '16px', borderLeft: '3px solid var(--red-closer)' }}>
                  <div className="eyebrow eyebrow-closer">RECOMENDAÇÃO TÁTICA PARA O CLOSER</div>
                  <p style={{ fontWeight: 600, marginTop: '6px' }}>
                    {lead.dossie_comercial.proximo_passo.acao_sugerida} (
                    {lead.dossie_comercial.proximo_passo.quando_retomar})
                  </p>
                  <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '4px' }}>
                    Dica de Ouro: {lead.dossie_comercial.proximo_passo.dica_de_ouro}
                  </p>
                </div>
              )}
            </>
          ) : (
            <>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                  gap: '12px',
                }}
              >
                <div className="surface-elevated" style={{ padding: '14px' }}>
                  <div className="eyebrow">PIPELINE EM ABERTO</div>
                  <div className="mono-metric" style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px' }}>
                    {formatCurrencyBRL(totalPipeline)}
                  </div>
                </div>
                <div className="surface-elevated" style={{ padding: '14px' }}>
                  <div className="eyebrow">RECEITA FECHADA</div>
                  <div
                    className="mono-metric"
                    style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px', color: 'var(--emerald-won)' }}
                  >
                    {formatCurrencyBRL(totalWon)}
                  </div>
                </div>
                <div className="surface-elevated" style={{ padding: '14px' }}>
                  <div className="eyebrow">PRIORIDADE HUMANA / QUENTES</div>
                  <div
                    className="mono-metric"
                    style={{ fontSize: '18px', fontWeight: 700, marginTop: '4px', color: 'var(--red-closer)' }}
                  >
                    {hotLeads.length} lead(s)
                  </div>
                </div>
              </div>

              <div>
                <div className="eyebrow" style={{ marginBottom: '10px' }}>
                  OPORTUNIDADES PRIORITÁRIAS PARA REUNIÃO DE PIPELINE
                </div>
                <table className="ledger-table">
                  <thead>
                    <tr>
                      <th>Lead</th>
                      <th>Etapa</th>
                      <th>Controle</th>
                      <th>Valor Estimado</th>
                      <th>Entrada</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(hotLeads.length > 0 ? hotLeads : leads).slice(0, 12).map((item) => (
                      <tr key={item.id}>
                        <td>
                          <div style={{ fontWeight: 600 }}>{item.nome || 'Sem nome'}</div>
                          <div className="mono-metric" style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                            {item.telefone}
                          </div>
                        </td>
                        <td>{getEtapaLabel(item.etapa_funil)}</td>
                        <td>{getControleLabel(item.controle)}</td>
                        <td className="mono-metric">{formatCurrencyBRL(item.valor_estimado)}</td>
                        <td className="mono-metric" style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          {formatDateTimeBR(item.criado_em)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
