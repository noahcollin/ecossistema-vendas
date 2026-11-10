import React from 'react';
import type { FunilKPIs } from '../../types/analytics';
import type { EtapaFunil } from '../../types/telemetry';
import { formatCurrencyBRL, getEtapaLabel } from '../../utils/formatters';

interface FunnelConduitSectionProps {
  funil: FunilKPIs;
}

const ORDERED_STAGES: EtapaFunil[] = [
  'NOVO_CONTATO',
  'QUALIFICACAO',
  'NEGOCIACAO',
  'FECHAMENTO',
];

export const FunnelConduitSection: React.FC<FunnelConduitSectionProps> = ({ funil }) => {
  const stageMap = new Map(funil.por_etapa.map((item) => [item.etapa, item]));

  return (
    <section className="surface-panel" aria-label="Esteira de Vendas 4D">
      <div className="panel-header">
        <div>
          <div className="eyebrow">ESTEIRA COGNITIVA DE VENDAS (FSM)</div>
          <h2 className="section-title" style={{ marginTop: '2px' }}>
            Distribuição Volumétrica &amp; Capital por Estágio
          </h2>
        </div>
        <span className="badge badge-closer">
          {funil.leads_quentes_count} LEAD(S) QUENTE(S)
        </span>
      </div>

      <div className="funnel-grid-4">
        {ORDERED_STAGES.map((stage, index) => {
          const data = stageMap.get(stage);
          const count = data?.quantidade ?? 0;
          const capital = data?.valor_total_reais ?? 0;
          const sharePct = data?.percentual_base ?? 0;
          const isClosingStage = stage === 'NEGOCIACAO' || stage === 'FECHAMENTO';

          return (
            <div key={stage} className="funnel-stage-cell">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="eyebrow">
                  0{index + 1} · {getEtapaLabel(stage).toUpperCase()}
                </span>
                <span className="mono-metric" style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
                  {sharePct.toFixed(1)}% da base
                </span>
              </div>

              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: '8px' }}>
                <span className="mono-metric" style={{ fontSize: '26px', fontWeight: 700 }}>
                  {count}
                </span>
                <span
                  className="mono-metric"
                  style={{
                    fontSize: '13px',
                    fontWeight: 600,
                    color: isClosingStage ? 'var(--text-primary)' : 'var(--text-muted)',
                  }}
                >
                  {formatCurrencyBRL(capital)}
                </span>
              </div>

              <div
                style={{
                  height: '3px',
                  width: '100%',
                  background: 'var(--bg-surface-2)',
                  borderRadius: '2px',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    height: '100%',
                    width: `${Math.min(100, Math.max(count > 0 ? 8 : 0, sharePct))}%`,
                    background:
                      stage === 'FECHAMENTO'
                        ? 'var(--red-closer)'
                        : stage === 'NEGOCIACAO'
                          ? '#7B38A8'
                          : 'var(--blue-ai-bright)',
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};

