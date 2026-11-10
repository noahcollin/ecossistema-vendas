import React from 'react';
import type { LeadQualificationViewModel } from '../../mappers/leadMapper';
import type { FollowupAgendado, Lead } from '../../types/telemetry';
import { formatDateTimeBR, getEtapaLabel } from '../../utils/formatters';

interface DossierFinancialTabProps {
  lead: Lead;
  vm: LeadQualificationViewModel;
  followups: FollowupAgendado[];
}

export const DossierFinancialTab: React.FC<DossierFinancialTabProps> = ({
  lead,
  vm,
  followups,
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
        <div className="surface-elevated" style={{ padding: '16px' }}>
          <div className="eyebrow eyebrow-ai">VALOR ESTIMADO DO DEAL</div>
          <div className="mono-metric" style={{ fontSize: '24px', fontWeight: 700, marginTop: '6px' }}>
            {vm.valorEstimadoFormatado}
          </div>
        </div>

        <div className="surface-elevated" style={{ padding: '16px' }}>
          <div className="eyebrow">ORÇAMENTO DECLARADO</div>
          <div style={{ fontSize: '15px', fontWeight: 600, marginTop: '8px' }}>
            {vm.orcamentoDeclarado}
          </div>
        </div>

        <div className="surface-elevated" style={{ padding: '16px' }}>
          <div className="eyebrow">PRAZO / URGÊNCIA</div>
          <div style={{ fontSize: '15px', fontWeight: 600, marginTop: '8px' }}>
            {vm.prazoImplementacao}
          </div>
        </div>

        <div className="surface-elevated" style={{ padding: '16px' }}>
          <div className="eyebrow">VOLUME DE LEADS &amp; STACK ATUAL</div>
          <div style={{ fontSize: '13.5px', fontWeight: 600, marginTop: '8px' }}>
            {vm.volumeLeadsMes} · {vm.ferramentaAtual}
          </div>
        </div>
      </div>

      {lead.motivo_perda && (
        <div className="alert-banner is-error" style={{ marginBottom: 0 }}>
          <span>
            <strong>Motivo de Perda / Congelamento Registrado:</strong> {lead.motivo_perda}
          </span>
        </div>
      )}

      {/* Histórico Real do Motor de Cadência Temporal */}
      <div className="surface-panel">
        <div className="panel-header" style={{ padding: '14px 16px' }}>
          <span className="eyebrow">MOTOR DE CADÊNCIA &amp; FOLLOW-UP TEMPORAL</span>
          <span className="mono-metric" style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
            {followups.length} registro(s)
          </span>
        </div>

        {followups.length === 0 ? (
          <div style={{ padding: '20px', color: 'var(--text-muted)', fontSize: '13px' }}>
            Nenhum toque de follow-up registrado para este lead até o momento.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="ledger-table">
              <thead>
                <tr>
                  <th>Toque</th>
                  <th>Etapa</th>
                  <th>Status</th>
                  <th>Agendado Para</th>
                  <th>Mensagem Disparada</th>
                </tr>
              </thead>
              <tbody>
                {followups.map((f) => {
                  const statusClass =
                    f.status === 'DISPARADO'
                      ? 'badge-ai'
                      : f.status === 'PENDENTE'
                        ? 'badge-warm'
                        : f.status === 'CANCELADO_POR_RESPOSTA'
                          ? 'badge-won'
                          : 'badge-muted';

                  return (
                    <tr key={f.id}>
                      <td className="mono-metric">#{f.tentativa}</td>
                      <td>{getEtapaLabel(f.etapa_funil)}</td>
                      <td>
                        <span className={`badge ${statusClass}`}>{f.status}</span>
                      </td>
                      <td className="mono-metric" style={{ fontSize: '12px' }}>
                        {formatDateTimeBR(f.agendado_para)}
                      </td>
                      <td style={{ color: 'var(--text-secondary)', maxWidth: '320px' }}>
                        {f.mensagem_disparada || '—'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

