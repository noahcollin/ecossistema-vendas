import React from 'react'
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from 'recharts'

// Dados da Curva de Tração Comercial (Novos Leads vs Fechamentos)
const TRACTION_DATA = [
  { dia: '01/Out', novosLeads: 18, propostasFechadas: 4 },
  { dia: '02/Out', novosLeads: 24, propostasFechadas: 7 },
  { dia: '03/Out', novosLeads: 22, propostasFechadas: 6 },
  { dia: '04/Out', novosLeads: 31, propostasFechadas: 11 },
  { dia: '05/Out', novosLeads: 28, propostasFechadas: 9 },
  { dia: '06/Out', novosLeads: 39, propostasFechadas: 14 },
  { dia: '07/Out', novosLeads: 42, propostasFechadas: 16 },
]

// Dados do Donut Chart (Temperatura do Pipeline)
const TEMPERATURE_DATA = [
  { name: 'Leads Quentes (Fechamento Iminente)', value: 45, color: '#FF1E46', count: 64 },
  { name: 'Leads Mornos (Avaliando Proposta)', value: 35, color: '#0052FF', count: 50 },
  { name: 'Em Cadência de Follow-up (Resgate)', value: 20, color: '#334155', count: 28 },
]

// Dados das Objeções Mapeadas pelo Closer
const OBJECTIONS_DATA = [
  { objecao: 'Taxa de Juros / Financiamento', taxa: 41 },
  { objecao: 'Dúvidas de Homologação', taxa: 28 },
  { objecao: 'Comparando com Concorrente', taxa: 19 },
  { objecao: 'Prazo de Instalação', taxa: 12 },
]

// Últimos Negócios e Ocorrências Comerciais
const RECENT_DEALS = [
  {
    hora: '16:42',
    cliente: 'Carlos Eduardo Mendes',
    tel: '+55 83 98888-0001',
    valor: 'R$ 34.000',
    status: 'PROPOSTA ENVIADA',
    detalhe: 'Sistema 10kWp calculado com payback de 3.2 anos. Lead muito receptivo.',
    tipo: 'proposta',
  },
  {
    hora: '16:38',
    cliente: 'Mariana Silveira (Clínica)',
    tel: '+55 83 99912-3456',
    valor: 'R$ 78.000',
    status: 'RESGATADO POR FOLLOW-UP',
    detalhe: 'Respondeu ao 2º toque de cadência solicitando simulação de crédito bancário.',
    tipo: 'resgate',
  },
  {
    hora: '16:31',
    cliente: 'Roberto Dias Castro',
    tel: '+55 83 98765-4321',
    valor: 'R$ 48.000',
    status: 'CONTRATO FECHADO',
    detalhe: 'Contrato anual Demand AI + Agente WhatsApp assinado e setup faturado.',
    tipo: 'fechamento',
  },
]

export const OverviewView: React.FC = () => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
      {/* 1. SEÇÃO DE MANCHETE EXECUTIVA */}
      <section style={{ borderBottom: '1.5px solid var(--border-rule)', paddingBottom: '28px' }}>
        <div className="business-label" style={{ marginBottom: '10px', color: 'var(--blue-prime)' }}>
          INTELIGÊNCIA DE RECEITA & TRAÇÃO DE VENDAS
        </div>
        <h1 className="business-title-giant">
          R$ 434.000 EM NEGOCIAÇÃO ATIVA
        </h1>
        <p style={{ fontSize: '20px', color: 'var(--text-muted)', marginTop: '12px' }}>
          Pipeline comercial consolidado de 142 leads com ciclo médio de fechamento de 3.8 dias.
        </p>

        {/* Linha de Transição Híbrida Suave: Azul ➔ Vermelho */}
        <div style={{ marginTop: '22px', height: '4px', background: 'var(--dual-gradient)', borderRadius: '2px' }} />
      </section>

      {/* 2. OS 4 GRANDES NÚMEROS DO NEGÓCIO */}
      <section
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '24px',
        }}
      >
        {/* Card 1: Faturamento Fechado */}
        <div className="business-card-blue">
          <div className="business-label" style={{ color: '#93c5fd' }}>
            FATURAMENTO REALIZADO (MÊS)
          </div>
          <div className="business-metric-giant" style={{ margin: '14px 0 6px 0', color: '#ffffff' }}>
            R$ 184.000
          </div>
          <div style={{ fontSize: '15px', fontWeight: 700, color: '#60a5fa' }}>
            +22.4% vs mês anterior
          </div>
          <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginTop: '8px' }}>
            Volume líquido de contratos de IA e automações assinados no período.
          </p>
        </div>

        {/* Card 2: Pipeline em Negociação */}
        <div className="business-card">
          <div className="business-label">
            PIPELINE EM NEGOCIAÇÃO
          </div>
          <div className="business-metric-giant" style={{ margin: '14px 0 6px 0' }}>
            R$ 434.000
          </div>
          <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--blue-prime)' }}>
            142 oportunidades em curso
          </div>
          <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginTop: '8px' }}>
            Propostas abertas com chances reais de conversão.
          </p>
        </div>

        {/* Card 3: Receita Resgatada pela Cadência (ROI do Follow-up) */}
        <div className="business-card-dual">
          <div className="business-label" style={{ color: '#fed7aa' }}>
            RECEITA RESGATADA (FOLLOW-UP)
          </div>
          <div className="business-metric-giant" style={{ margin: '14px 0 6px 0', color: '#ffffff' }}>
            R$ 96.000
          </div>
          <div style={{ fontSize: '15px', fontWeight: 800, color: '#fb923c' }}>
            42% de taxa de reengajamento
          </div>
          <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginTop: '8px' }}>
            Negócios salvos pelo motor automático após o cliente esfriar.
          </p>
        </div>

        {/* Card 4: Ticket Médio & Ciclo de Venda */}
        <div className="business-card">
          <div className="business-label">
            TICKET MÉDIO DO CONTRATO
          </div>
          <div className="business-metric-giant" style={{ margin: '14px 0 6px 0' }}>
            R$ 38.500
          </div>
          <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-headline)' }}>
            Tempo médio: 3.8 dias p/ fechamento
          </div>
          <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginTop: '8px' }}>
            Velocidade comercial acelerada com qualificação instantânea.
          </p>
        </div>
      </section>

      {/* 3. GRÁFICO PRINCIPAL: CURVA DE TRAÇÃO COMERCIAL COM GRADIENTES SUAVES */}
      <section className="business-card" style={{ padding: '36px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: '28px' }}>
          <div>
            <h2 className="business-title-large">
              Curva de Tração Comercial & Fechamentos
            </h2>
            <p style={{ fontSize: '16px', color: 'var(--text-muted)', marginTop: '6px' }}>
              Entrada de novos leads qualificados versus volume de propostas fechadas por dia.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '28px', fontSize: '14px', fontWeight: 800, textTransform: 'uppercase' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ width: '16px', height: '16px', backgroundColor: 'var(--blue-prime)' }} />
              <span>Novos Leads</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ width: '16px', height: '16px', backgroundColor: 'var(--red-prime)' }} />
              <span>Propostas Fechadas</span>
            </div>
          </div>
        </div>

        <div style={{ height: '380px', width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={TRACTION_DATA} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="areaGradientAzul" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0052FF" stopOpacity={0.65} />
                  <stop offset="95%" stopColor="#0052FF" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="areaGradientVermelho" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#FF1E46" stopOpacity={0.65} />
                  <stop offset="95%" stopColor="#FF1E46" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1f1f2e" vertical={false} />
              <XAxis
                dataKey="dia"
                stroke="#64748b"
                tick={{ fill: '#94a3b8', fontSize: 13, fontFamily: 'Plus Jakarta Sans', fontWeight: 600 }}
                axisLine={{ stroke: '#272738' }}
              />
              <YAxis
                stroke="#64748b"
                tick={{ fill: '#94a3b8', fontSize: 13, fontFamily: 'Plus Jakarta Sans', fontWeight: 600 }}
                axisLine={{ stroke: '#272738' }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0E0E14',
                  border: '1.5px solid #272738',
                  borderRadius: '0px',
                  fontFamily: 'Plus Jakarta Sans',
                  fontSize: '14px',
                  fontWeight: 600,
                  boxShadow: '4px 4px 0px #000000',
                }}
              />
              <Area
                type="monotone"
                dataKey="novosLeads"
                name="Novos Leads"
                stroke="#0052FF"
                strokeWidth={3.5}
                fillOpacity={1}
                fill="url(#areaGradientAzul)"
              />
              <Area
                type="monotone"
                dataKey="propostasFechadas"
                name="Fechamentos"
                stroke="#FF1E46"
                strokeWidth={3.5}
                fillOpacity={1}
                fill="url(#areaGradientVermelho)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>

      {/* 4. DOIS GRÁFICOS VISUAIS DE ALTO IMPACTO (DONUT DE TEMPERATURA + BARRAS DE OBJEÇÕES) */}
      <section style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr', gap: '32px' }}>
        {/* Gráfico 2: Donut / Pie Chart de Temperatura do Pipeline */}
        <div className="business-card" style={{ padding: '36px' }}>
          <div className="business-label" style={{ marginBottom: '8px' }}>
            SAÚDE DO PIPELINE
          </div>
          <h2 className="business-title-large" style={{ marginBottom: '6px' }}>
            Temperatura dos Leads
          </h2>
          <p style={{ fontSize: '15px', color: 'var(--text-muted)', marginBottom: '24px' }}>
            Distribuição dos 142 leads pela prontidão de compra.
          </p>

          <div style={{ height: '240px', width: '100%', position: 'relative' }}>
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0E0E14',
                    border: '1.5px solid #272738',
                    borderRadius: '0px',
                    fontFamily: 'Plus Jakarta Sans',
                    fontSize: '14px',
                    fontWeight: 600,
                  }}
                />
                <Pie
                  data={TEMPERATURE_DATA}
                  cx="50%"
                  cy="50%"
                  innerRadius={70}
                  outerRadius={100}
                  paddingAngle={5}
                  dataKey="value"
                  stroke="#08080A"
                  strokeWidth={2}
                >
                  {TEMPERATURE_DATA.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>

            {/* Número Monumental no Centro do Donut */}
            <div
              style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                textAlign: 'center',
                pointerEvents: 'none',
              }}
            >
              <div style={{ fontSize: '32px', fontWeight: 900, fontFamily: 'var(--font-title)', lineHeight: 1 }}>
                142
              </div>
              <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: '4px' }}>
                LEADS
              </div>
            </div>
          </div>

          {/* Legenda Explicativa com Números Reais */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', marginTop: '24px' }}>
            {TEMPERATURE_DATA.map((item, idx) => (
              <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div style={{ width: '12px', height: '12px', backgroundColor: item.color }} />
                  <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-body)' }}>
                    {item.name}
                  </span>
                </div>
                <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-headline)', fontFamily: 'var(--font-mono)' }}>
                  {item.count} leads ({item.value}%)
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Gráfico 3: Termômetro de Objeções (Bar Chart com Gradiente) */}
        <div className="business-card" style={{ padding: '36px' }}>
          <div className="business-label" style={{ marginBottom: '8px' }}>
            INTELIGÊNCIA DO CLOSER
          </div>
          <h2 className="business-title-large" style={{ marginBottom: '6px' }}>
            Principais Objeções do Momento
          </h2>
          <p style={{ fontSize: '15px', color: 'var(--text-muted)', marginBottom: '24px' }}>
            Dúvidas mais recorrentes mapeadas pela IA para orientar o discurso comercial.
          </p>

          <div style={{ height: '240px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={OBJECTIONS_DATA}
                layout="vertical"
                margin={{ top: 10, right: 30, left: 60, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="barGradientDual" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor="#0052FF" />
                    <stop offset="100%" stopColor="#FF1E46" />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#1f1f2e" horizontal={false} />
                <XAxis
                  type="number"
                  domain={[0, 50]}
                  unit="%"
                  stroke="#64748b"
                  tick={{ fill: '#94a3b8', fontSize: 13, fontFamily: 'Plus Jakarta Sans', fontWeight: 600 }}
                />
                <YAxis
                  type="category"
                  dataKey="objecao"
                  stroke="#64748b"
                  tick={{ fill: '#e2e8f0', fontSize: 13, fontFamily: 'Plus Jakarta Sans', fontWeight: 700 }}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0E0E14',
                    border: '1.5px solid #272738',
                    borderRadius: '0px',
                    fontFamily: 'Plus Jakarta Sans',
                    fontSize: '14px',
                    fontWeight: 600,
                  }}
                  formatter={(value: any) => [`${value}% dos leads`, 'Frequência']}
                />
                <Bar
                  dataKey="taxa"
                  fill="url(#barGradientDual)"
                  radius={0}
                  barSize={24}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div
            style={{
              marginTop: '24px',
              padding: '16px 20px',
              backgroundColor: 'var(--blue-surface)',
              border: '1.5px solid var(--blue-border)',
            }}
          >
            <div style={{ fontSize: '13px', fontWeight: 800, color: '#93c5fd', textTransform: 'uppercase' }}>
              INSIGHT DA IA // RECOMENDAÇÃO PRÁTICA:
            </div>
            <p style={{ fontSize: '14px', color: '#ffffff', marginTop: '6px', lineHeight: 1.6 }}>
              41% dos clientes travam na taxa de juros. Ao oferecer a simulação onde a parcela mensal é menor do que a economia imediata da conta de luz, a taxa de fechamento sobe para 68%.
            </p>
          </div>
        </div>
      </section>

      {/* 5. ÚLTIMOS NEGÓCIOS & OCORRÊNCIAS COMERCIAIS */}
      <section style={{ borderTop: '1.5px solid var(--border-rule)', paddingTop: '32px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '20px' }}>
          <div>
            <h2 className="business-title-large">
              Últimas Ocorrências Comerciais
            </h2>
            <p style={{ fontSize: '15px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Feed em tempo real de propostas geradas, resgates de follow-up e contratos fechados.
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {RECENT_DEALS.map((deal, idx) => (
            <div
              key={idx}
              style={{
                display: 'grid',
                gridTemplateColumns: '80px 260px 140px 220px 1fr',
                padding: '22px 0',
                borderBottom: '1px solid var(--border-rule)',
                alignItems: 'baseline',
                fontSize: '15px',
              }}
            >
              <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                {deal.hora}
              </span>
              <div>
                <div style={{ fontWeight: 800, color: 'var(--text-headline)', fontSize: '16px' }}>
                  {deal.cliente}
                </div>
                <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '13px', marginTop: '2px' }}>
                  {deal.tel}
                </div>
              </div>
              <span
                style={{
                  fontFamily: 'var(--font-title)',
                  fontSize: '18px',
                  fontWeight: 900,
                  color: deal.tipo === 'fechamento' ? '#22c55e' : 'var(--text-headline)',
                }}
              >
                {deal.valor}
              </span>
              <span
                style={{
                  fontSize: '12px',
                  fontWeight: 800,
                  textTransform: 'uppercase',
                  color:
                    deal.tipo === 'fechamento'
                      ? '#22c55e'
                      : deal.tipo === 'resgate'
                      ? '#fb923c'
                      : 'var(--blue-prime)',
                }}
              >
                {deal.status}
              </span>
              <span style={{ color: 'var(--text-body)', fontSize: '14px', lineHeight: 1.5 }}>
                {deal.detalhe}
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}
