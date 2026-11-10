import React from 'react';
import type { DashboardOverviewResponse } from '../../types/analytics';
import type { Lead } from '../../types/telemetry';
import { formatCurrencyBRL } from '../../utils/formatters';

interface HeroThesisSectionProps {
  overview: DashboardOverviewResponse;
  leads: Lead[];
  pendingHandoverCount: number;
  onNavigateToHandover: () => void;
}

export const HeroThesisSection: React.FC<HeroThesisSectionProps> = ({
  overview,
  leads,
  pendingHandoverCount,
  onNavigateToHandover,
}) => {
  const { financeiro, conversas } = overview;

  const totalActive = leads.filter((l) => l.desfecho === 'EM_ANDAMENTO').length || 1;
  const aiPilotCount = leads.filter(
    (l) => l.desfecho === 'EM_ANDAMENTO' && l.controle === 'PILOTO_IA'
  ).length;
  const aiSharePct = Math.round((aiPilotCount / totalActive) * 100);
  const humanSharePct = Math.max(0, 100 - aiSharePct);

  return (
    <section className="hero-thesis-grid" aria-label="Tese Financeira do Pipeline">
      <div className="hero-primary-cell">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
            <span className="eyebrow eyebrow-ai">CAPITAL ATIVO EM NEGOCIAÇÃO</span>
            {pendingHandoverCount > 0 && (
              <button
                type="button"
                className="btn btn-sm btn-outline-closer"
                onClick={onNavigateToHandover}
              >
                <span>{pendingHandoverCount} aguardando Closer</span>
              </button>
            )}
          </div>

          <div
            className="headline-display mono-metric"
            style={{ fontSize: 'clamp(32px, 4vw, 46px)', marginTop: '10px' }}
          >
            {formatCurrencyBRL(financeiro.pipeline_ativo_reais)}
          </div>

          <p style={{ color: 'var(--text-muted)', fontSize: '13.5px', marginTop: '8px', maxWidth: '58ch' }}>
            Distribuído em <strong style={{ color: 'var(--text-primary)' }}>{financeiro.total_leads_em_andamento}</strong>{' '}
            negociações ativas de um total de{' '}
            <strong style={{ color: 'var(--text-primary)' }}>{overview.total_leads_cadastrados}</strong>{' '}
            leads auditados pelo ecossistema.
          </p>
        </div>

        <div>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '11.5px',
              marginBottom: '6px',
            }}
          >
            <span className="mono-metric" style={{ color: 'var(--blue-ai-bright)' }}>
              PILOTO IA: {aiSharePct}%
            </span>
            <span className="mono-metric" style={{ color: 'var(--red-closer)' }}>
              CLOSER HUMANO: {humanSharePct}%
            </span>
          </div>
          <div
            style={{
              height: '6px',
              width: '100%',
              borderRadius: '99px',
              background: 'var(--bg-surface-2)',
              overflow: 'hidden',
            }}
          >
            <div className="prestige-beam" style={{ height: '100%' }} />
          </div>
        </div>
      </div>

      <div className="hero-kpi-rail">
        <div className="hero-kpi-cell">
          <span className="eyebrow">RECEITA CONQUISTADA</span>
          <div
            className="mono-metric"
            style={{ fontSize: '22px', fontWeight: 700, color: 'var(--emerald-won)' }}
          >
            {formatCurrencyBRL(financeiro.receita_ganha_reais)}
          </div>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {financeiro.total_leads_ganhos} contrato(s) fechado(s)
          </span>
        </div>

        <div className="hero-kpi-cell">
          <span className="eyebrow">TICKET MÉDIO REALIZADO</span>
          <div className="mono-metric" style={{ fontSize: '22px', fontWeight: 700 }}>
            {financeiro.total_leads_ganhos > 0
              ? formatCurrencyBRL(financeiro.ticket_medio_reais)
              : '—'}
          </div>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Conversão: {financeiro.taxa_conversao_pct.toFixed(1)}% dos finalizados
          </span>
        </div>

        <div className="hero-kpi-cell">
          <span className="eyebrow">EFICÁCIA DE RESGATE (CADÊNCIA)</span>
          <div
            className="mono-metric"
            style={{ fontSize: '22px', fontWeight: 700, color: 'var(--blue-ai-bright)' }}
          >
            {conversas.eficacia_followup.taxa_resgate_pct.toFixed(1)}%
          </div>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {conversas.eficacia_followup.total_resgatados_por_resposta} resgatado(s) /{' '}
            {conversas.eficacia_followup.total_disparados} toque(s)
          </span>
        </div>

        <div className="hero-kpi-cell">
          <span className="eyebrow">CAPITAL PERDIDO / CONGELADO</span>
          <div
            className="mono-metric"
            style={{ fontSize: '22px', fontWeight: 700, color: 'var(--red-closer)' }}
          >
            {formatCurrencyBRL(financeiro.valor_perdido_reais)}
          </div>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {financeiro.total_leads_perdidos} encerrado(s) sem conversão
          </span>
        </div>
      </div>
    </section>
  );
};

