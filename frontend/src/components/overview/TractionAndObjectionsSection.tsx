import React from 'react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type {
  AquisicaoKPIs,
  FunilKPIs,
  PerdasKPIs,
  TimeRange,
  TractionPoint,
} from '../../types/analytics';
import {
  formatCurrencyBRL,
  getCanalLabel,
  getTemperaturaLabel,
} from '../../utils/formatters';

interface TractionAndObjectionsSectionProps {
  tractionData: TractionPoint[];
  timeRange: TimeRange;
  onChangeTimeRange: (range: TimeRange) => void;
  funil: FunilKPIs;
  aquisicao: AquisicaoKPIs;
  perdas: PerdasKPIs;
}

const TIME_OPTIONS: { value: TimeRange; label: string }[] = [
  { value: '24h', label: '24H' },
  { value: '7d', label: '7D' },
  { value: '30d', label: '30D' },
];

export const TractionAndObjectionsSection: React.FC<TractionAndObjectionsSectionProps> = ({
  tractionData,
  timeRange,
  onChangeTimeRange,
  funil,
  aquisicao,
  perdas,
}) => {
  return (
    <div className="overview-two-col">
      {/* Coluna Esquerda: Curva de Tração Temporal */}
      <section className="surface-panel" style={{ display: 'flex', flexDirection: 'column' }}>
        <div className="panel-header">
          <div>
            <div className="eyebrow eyebrow-ai">RITMO DE CAPTAÇÃO &amp; FECHAMENTO</div>
            <h2 className="section-title" style={{ marginTop: '2px' }}>
              Tração Comercial na Janela Selecionada
            </h2>
          </div>

          <div style={{ display: 'flex', gap: '4px' }}>
            {TIME_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`btn btn-sm mono-metric ${timeRange === opt.value ? 'btn-ai' : ''}`}
                onClick={() => onChangeTimeRange(opt.value)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        <div className="panel-body" style={{ flex: 1, minHeight: '270px' }}>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={tractionData} margin={{ top: 8, right: 12, left: -18, bottom: 0 }}>
              <defs>
                <linearGradient id="aiInboundFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0052FF" stopOpacity={0.32} />
                  <stop offset="95%" stopColor="#0052FF" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="closerDealFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#FF1E46" stopOpacity={0.28} />
                  <stop offset="95%" stopColor="#FF1E46" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E2336" vertical={false} />
              <XAxis
                dataKey="label"
                stroke="#5A647E"
                tick={{ fill: '#8B97B0', fontSize: 11, fontFamily: 'JetBrains Mono' }}
              />
              <YAxis
                allowDecimals={false}
                stroke="#5A647E"
                tick={{ fill: '#8B97B0', fontSize: 11, fontFamily: 'JetBrains Mono' }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#121522',
                  borderColor: '#2D3552',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
              />
              <Area
                type="monotone"
                dataKey="entradas"
                name="Entradas Qualificadas"
                stroke="#1E6BFF"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#aiInboundFill)"
              />
              <Area
                type="monotone"
                dataKey="fechamentos"
                name="Em Fechamento / Ganhos"
                stroke="#FF1E46"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#closerDealFill)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* Coluna Direita: Termômetro, Canais & Diagnóstico de Perdas */}
      <section className="surface-panel" style={{ display: 'flex', flexDirection: 'column', gap: '18px', padding: '20px 22px' }}>
        <div>
          <div className="eyebrow">TERMÔMETRO DA CARTEIRA</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', marginTop: '10px' }}>
            {(['QUENTE', 'MORNO', 'FRIO'] as const).map((temp) => {
              const found = funil.por_temperatura.find((t) => t.temperatura === temp);
              const badgeClass =
                temp === 'QUENTE'
                  ? 'badge-closer'
                  : temp === 'MORNO'
                    ? 'badge-warm'
                    : 'badge-muted';
              return (
                <div key={temp} className="surface-elevated" style={{ padding: '10px 12px' }}>
                  <span className={`badge ${badgeClass}`}>{getTemperaturaLabel(temp)}</span>
                  <div className="mono-metric" style={{ fontSize: '19px', fontWeight: 700, marginTop: '6px' }}>
                    {found?.quantidade ?? 0}
                  </div>
                  <div className="mono-metric" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    {(found?.percentual ?? 0).toFixed(1)}%
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--border-rule)', paddingTop: '14px' }}>
          <div className="eyebrow">CANAIS DE AQUISIÇÃO &amp; CONVERSÃO</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '10px' }}>
            {aquisicao.por_canal.length === 0 ? (
              <span style={{ color: 'var(--text-muted)', fontSize: '12.5px' }}>
                Nenhum canal registrado até o momento.
              </span>
            ) : (
              aquisicao.por_canal.slice(0, 3).map((canal) => (
                <div
                  key={canal.origem_canal}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12.5px' }}
                >
                  <span style={{ fontWeight: 500 }}>{getCanalLabel(canal.origem_canal)}</span>
                  <span className="mono-metric" style={{ color: 'var(--text-secondary)' }}>
                    {canal.total_leads} leads · {canal.taxa_conversao_pct.toFixed(0)}% conv.
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--border-rule)', paddingTop: '14px' }}>
          <div className="eyebrow eyebrow-closer">PRINCIPAIS MOTIVOS DE PERDA / OBJEÇÃO</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '10px' }}>
            {perdas.motivos_ranking.length === 0 ? (
              <span style={{ color: 'var(--text-muted)', fontSize: '12.5px' }}>
                Zero descartes registrados no período.
              </span>
            ) : (
              perdas.motivos_ranking.slice(0, 3).map((item) => (
                <div
                  key={item.motivo}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12.5px' }}
                >
                  <span style={{ color: 'var(--text-secondary)' }}>{item.motivo}</span>
                  <span className="mono-metric" style={{ color: 'var(--red-closer)' }}>
                    {item.quantidade}x ({formatCurrencyBRL(item.valor_perdido_reais)})
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </section>
    </div>
  );
};

