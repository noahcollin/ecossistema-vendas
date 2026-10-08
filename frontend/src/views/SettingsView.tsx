import React, { useState, useEffect } from 'react'
import type {
  OperacaoSettings,
  ProdutoItem,
  PacingConfig,
  IntegracoesConfig,
} from '../types/settings'
import { fetchOperacaoSettings, updateOperacaoSettings } from '../services/api'

// Valores Padrão Operacionais da Inteligentte
const DEFAULT_PACING: PacingConfig = {
  quebra_baloes_ativa: true,
  transbordo_pedido_humano: true,
  transbordo_duvida_lgpd: true,
  transbordo_desconto_alto: true,
}

const DEFAULT_INTEGRACOES: IntegracoesConfig = {
  crm_ativo: 'KOMMO',
  whatsapp_conectado: true,
  whatsapp_numero: '+55 83 9192-3098',
  api_key_master: 'master-secret-key-123',
}

const DIAS_NOMES = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']

export const SettingsView: React.FC = () => {
  const [settings, setSettings] = useState<OperacaoSettings | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [saving, setSaving] = useState<boolean>(false)
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; msg: string } | null>(null)
  const [showApiKey, setShowApiKey] = useState<boolean>(false)
  const [isSilenced, setIsSilenced] = useState<boolean>(false)

  // 1. Carrega Configurações do Backend com Fallbacks Ricos
  const loadSettings = async () => {
    try {
      setLoading(true)
      const data = await fetchOperacaoSettings()
      setSettings({
        ...data,
        modo_24h_inbound: data.modo_24h_inbound ?? true,
        ia_silenciada_global: data.ia_silenciada_global ?? false,
        pacing: data.pacing || DEFAULT_PACING,
        integracoes: data.integracoes || DEFAULT_INTEGRACOES,
      })
      setIsSilenced(data.ia_silenciada_global ?? false)
    } catch (err: any) {
      setFeedback({ type: 'error', msg: `Erro ao sincronizar com backend: ${err.message}` })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSettings()
  }, [])

  // 2. Grava Alterações no Backend
  const handleSave = async () => {
    if (!settings) return
    try {
      setSaving(true)
      setFeedback(null)

      const payloadToSave: OperacaoSettings = {
        ...settings,
        ia_silenciada_global: isSilenced,
      }

      const updated = await updateOperacaoSettings(payloadToSave)
      setSettings({
        ...updated,
        modo_24h_inbound: updated.modo_24h_inbound ?? settings.modo_24h_inbound ?? true,
        ia_silenciada_global: isSilenced,
        pacing: settings.pacing,
        integracoes: settings.integracoes,
      })
      setFeedback({ type: 'success', msg: 'DIRETRIZES DA OPERAÇÃO SALVAS E ATUALIZADAS NO BACKEND COM SUCESSO.' })
      setTimeout(() => setFeedback(null), 4000)
    } catch (err: any) {
      setFeedback({ type: 'error', msg: `FALHA AO SALVAR CONFIGURAÇÕES: ${err.message}` })
    } finally {
      setSaving(false)
    }
  }

  // Métodos de Gestão de Produtos
  const handleUpdateProduct = (id: string, field: keyof ProdutoItem, val: any) => {
    if (!settings) return
    const updated = settings.produtos.map((p) =>
      p.id === id ? { ...p, [field]: val } : p
    )
    setSettings({ ...settings, produtos: updated })
  }

  const handleToggleProduct = (id: string) => {
    if (!settings) return
    const updated = settings.produtos.map((p) =>
      p.id === id ? { ...p, ativo: !p.ativo } : p
    )
    setSettings({ ...settings, produtos: updated })
  }

  const handleAddProduct = () => {
    if (!settings) return
    const newProd: ProdutoItem = {
      id: `solucao_${Date.now()}`,
      nome: 'Nova Solução de IA Inteligentte',
      descricao: 'Descrição comercial da solução de inteligência artificial ou automação.',
      preco_base_mensal: 2500,
      taxa_setup: 1000,
      ativo: true,
    }
    setSettings({ ...settings, produtos: [...settings.produtos, newProd] })
  }

  const handleDeleteProduct = (id: string) => {
    if (!settings) return
    const filtered = settings.produtos.filter((p) => p.id !== id)
    setSettings({ ...settings, produtos: filtered })
  }

  // Métodos de Dias da Semana
  const toggleDiaSemana = (dia: number) => {
    if (!settings) return
    const dias = settings.horario_comercial.dias_semana || []
    const newDias = dias.includes(dia) ? dias.filter((d) => d !== dia) : [...dias, dia]
    setSettings({
      ...settings,
      horario_comercial: { ...settings.horario_comercial, dias_semana: newDias.sort() },
    })
  }

  // Alternância do Kill-Switch Global
  const handleToggleKillSwitch = () => {
    const newState = !isSilenced
    setIsSilenced(newState)
    if (settings) {
      setSettings({ ...settings, ia_silenciada_global: newState })
    }
  }

  if (loading) {
    return (
      <div style={{ padding: '80px 0', textAlign: 'center' }}>
        <h2 className="business-title-medium">Carregando Diretrizes da Operação...</h2>
      </div>
    )
  }

  if (!settings) {
    return (
      <div className="business-card-red" style={{ padding: '32px' }}>
        <h2 className="business-title-medium">Falha de Conexão com o Backend</h2>
        <p style={{ marginTop: '8px', color: 'var(--text-body)' }}>
          Certifique-se de que a API do backend está ativa na porta 8000.
        </p>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '40px' }}>
      {/* =========================================================================
          1. HEADER EXECUTIVO BUSINESS BRUTALISTA
          ========================================================================= */}
      <section style={{ borderBottom: '1.5px solid var(--border-rule)', paddingBottom: '28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <div className="business-label" style={{ marginBottom: '8px', color: 'var(--blue-prime)' }}>
              POLÍTICAS COMERCIAIS & PARÂMETROS OPERACIONAIS
            </div>
            <h1 className="business-title-giant">
              DIRETRIZES DA OPERAÇÃO
            </h1>
            <p style={{ fontSize: '19px', color: 'var(--text-muted)', marginTop: '10px', maxWidth: '880px' }}>
              Parâmetros de precificação das soluções de IA, cadência de reengajamento, comportamento do Agente e integrações ativas.
            </p>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '12px' }}>
            <button
              onClick={handleSave}
              disabled={saving}
              className="btn-business btn-business-blue"
              style={{ padding: '16px 36px', fontSize: '15px' }}
            >
              {saving ? 'GRAVANDO NO SISTEMA...' : '💾 SALVAR ALTERAÇÕES'}
            </button>

            {/* Badges de Status do Sistema */}
            <div style={{ display: 'flex', gap: '8px' }}>
              <span className="badge-brutalist badge-green">SISTEMA: OPERACIONAL</span>
              <span className={`badge-brutalist ${isSilenced ? 'badge-red' : 'badge-blue'}`}>
                {isSilenced ? '🛑 IA SILENCIADA' : '⚡ MOTOR IA ATIVO'}
              </span>
            </div>
          </div>
        </div>

        {/* Linha de Transição Híbrida: Azul ➔ Vermelho */}
        <div style={{ marginTop: '24px', height: '4px', background: 'var(--dual-gradient)', borderRadius: '2px' }} />
      </section>

      {/* Banner de Feedback de Gravação */}
      {feedback && (
        <div
          className={feedback.type === 'success' ? 'business-card-blue' : 'business-card-red'}
          style={{ padding: '20px 28px', borderLeft: '6px solid #ffffff' }}
        >
          <div style={{ fontWeight: 800, fontSize: '16px', color: '#ffffff' }}>
            {feedback.msg}
          </div>
        </div>
      )}

      {/* =========================================================================
          2. SEÇÃO: CATÁLOGO DE SOLUÇÕES & PREÇOS OFICIAIS DA INTELIGENTTE
          ========================================================================= */}
      <section className="business-card" style={{ padding: '36px' }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'baseline',
            marginBottom: '28px',
            borderBottom: '1.5px solid var(--border-rule)',
            paddingBottom: '16px',
            flexWrap: 'wrap',
            gap: '12px',
          }}
        >
          <div>
            <div className="business-label" style={{ color: 'var(--blue-prime)', marginBottom: '4px' }}>
              PORTFÓLIO COMERCIAL & ÂNCORAS DE ROI
            </div>
            <h2 className="business-title-large">
              Catálogo de Soluções & Preços
            </h2>
            <p style={{ fontSize: '15px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Valores e condições que o consultor virtual (Seu Zé) utiliza para ancorar retorno financeiro e apresentar propostas.
            </p>
          </div>

          <button
            onClick={handleAddProduct}
            className="btn-business"
            style={{ padding: '12px 22px', fontSize: '13px' }}
          >
            + ADICIONAR SOLUÇÃO
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {settings.produtos.map((prod) => (
            <div
              key={prod.id}
              style={{
                padding: '26px 28px',
                backgroundColor: 'var(--bg-card-light)',
                border: prod.ativo ? '1.5px solid var(--border-rule)' : '1.5px solid rgba(255, 255, 255, 0.05)',
                opacity: prod.ativo ? 1 : 0.65,
                display: 'flex',
                flexDirection: 'column',
                gap: '16px',
                transition: 'all 150ms ease',
              }}
            >
              {/* Linha 1: Nome da Solução e Ações */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
                <input
                  type="text"
                  value={prod.nome}
                  onChange={(e) => handleUpdateProduct(prod.id, 'nome', e.target.value)}
                  className="input-business"
                  style={{
                    flex: 1,
                    fontFamily: 'var(--font-title)',
                    fontSize: '20px',
                    fontWeight: 800,
                    padding: '12px 18px',
                  }}
                />

                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    onClick={() => handleToggleProduct(prod.id)}
                    className="btn-business"
                    style={{
                      padding: '12px 20px',
                      fontSize: '12px',
                      backgroundColor: prod.ativo ? 'var(--blue-surface)' : 'var(--bg-void)',
                      borderColor: prod.ativo ? 'var(--blue-prime)' : 'var(--border-rule)',
                      color: prod.ativo ? '#60a5fa' : 'var(--text-muted)',
                    }}
                  >
                    {prod.ativo ? '✓ ATIVA' : 'PAUSADA'}
                  </button>

                  <button
                    onClick={() => handleDeleteProduct(prod.id)}
                    className="btn-business btn-business-red"
                    style={{ padding: '12px 20px', fontSize: '12px' }}
                  >
                    EXCLUIR
                  </button>
                </div>
              </div>

              {/* Linha 2: Descrição Comercial */}
              <input
                type="text"
                value={prod.descricao}
                onChange={(e) => handleUpdateProduct(prod.id, 'descricao', e.target.value)}
                placeholder="Descrição comercial resumida da solução..."
                className="input-business"
                style={{ fontSize: '15px', color: 'var(--text-body)' }}
              />

              {/* Linha 3: Mensalidade Base e Taxa de Setup */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '20px' }}>
                <div>
                  <div className="business-label" style={{ marginBottom: '8px' }}>
                    MENSALIDADE BASE (R$)
                  </div>
                  <input
                    type="number"
                    value={prod.preco_base_mensal}
                    onChange={(e) =>
                      handleUpdateProduct(prod.id, 'preco_base_mensal', parseFloat(e.target.value) || 0)
                    }
                    className="input-business"
                    style={{ fontSize: '18px', fontWeight: 800, fontFamily: 'var(--font-mono)' }}
                  />
                </div>

                <div>
                  <div className="business-label" style={{ marginBottom: '8px' }}>
                    TAXA DE SETUP / IMPLEMENTAÇÃO (R$)
                  </div>
                  <input
                    type="number"
                    value={prod.taxa_setup}
                    onChange={(e) =>
                      handleUpdateProduct(prod.id, 'taxa_setup', parseFloat(e.target.value) || 0)
                    }
                    className="input-business"
                    style={{ fontSize: '18px', fontWeight: 800, fontFamily: 'var(--font-mono)' }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* =========================================================================
          3. SEÇÃO: DINÂMICA CONVERSACIONAL & PACING DO AGENTE
          ========================================================================= */}
      <section className="business-card" style={{ padding: '36px' }}>
        <div style={{ marginBottom: '24px', borderBottom: '1.5px solid var(--border-rule)', paddingBottom: '16px' }}>
          <div className="business-label" style={{ color: 'var(--blue-prime)', marginBottom: '4px' }}>
            INTELIGÊNCIA COGNITIVA & COMPORTAMENTO DO WHATSAPP
          </div>
          <h2 className="business-title-large">
            Dinâmica Conversacional & Pacing do Agente
          </h2>
          <p style={{ fontSize: '15px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Regras de cadência instantânea, digitação humanizada e gatilhos de segurança para transbordo da equipe.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '28px' }}>
          {/* Card: Debounce de Mensagens */}
          <div style={{ padding: '24px', backgroundColor: 'var(--bg-card-light)', border: '1.5px solid var(--border-rule)' }}>
            <div className="business-label" style={{ marginBottom: '6px' }}>
              DEBOUNCE DE MENSAGENS (SEGUNDOS)
            </div>
            <div style={{ fontSize: '32px', fontWeight: 900, color: 'var(--blue-prime)', fontFamily: 'var(--font-mono)', margin: '8px 0' }}>
              {settings.debounce_segundos}s
            </div>
            <p style={{ fontSize: '14px', color: 'var(--text-muted)', marginBottom: '16px', lineHeight: 1.5 }}>
              Janela de espera para agrupar múltiplos áudios ou mensagens seguidas do cliente antes de formular a resposta unificada.
            </p>
            <input
              type="range"
              min="1.0"
              max="10.0"
              step="0.5"
              value={settings.debounce_segundos}
              onChange={(e) =>
                setSettings({
                  ...settings,
                  debounce_segundos: parseFloat(e.target.value),
                })
              }
              style={{ width: '100%', accentColor: 'var(--blue-prime)', cursor: 'pointer' }}
            />
          </div>

          {/* Card: Quebra de Balões Orgânicos */}
          <div style={{ padding: '24px', backgroundColor: 'var(--bg-card-light)', border: '1.5px solid var(--border-rule)' }}>
            <div className="business-label" style={{ marginBottom: '6px' }}>
              QUEBRA DE BALÕES ORGÂNICOS (|||)
            </div>
            <div style={{ fontSize: '18px', fontWeight: 800, marginTop: '8px', color: 'var(--text-headline)' }}>
              Digitação Humanizada em Múltiplos Balões
            </div>
            <p style={{ fontSize: '14px', color: 'var(--text-muted)', margin: '8px 0 16px 0', lineHeight: 1.5 }}>
              Divide mensagens longas em 2 a 3 balões dinâmicos usando o separador interno para simular conversa real no WhatsApp.
            </p>
            <button
              type="button"
              onClick={() =>
                setSettings({
                  ...settings,
                  pacing: {
                    ...settings.pacing!,
                    quebra_baloes_ativa: !settings.pacing?.quebra_baloes_ativa,
                  },
                })
              }
              className="btn-business"
              style={{
                width: '100%',
                fontSize: '13px',
                backgroundColor: settings.pacing?.quebra_baloes_ativa ? 'var(--blue-surface)' : 'var(--bg-void)',
                borderColor: settings.pacing?.quebra_baloes_ativa ? 'var(--blue-prime)' : 'var(--border-rule)',
                color: settings.pacing?.quebra_baloes_ativa ? '#60a5fa' : 'var(--text-muted)',
              }}
            >
              {settings.pacing?.quebra_baloes_ativa ? '✓ MÚLTIPLOS BALÕES ATIVOS' : 'BALÃO ÚNICO COMPRIDO'}
            </button>
          </div>

          {/* Card: Gatilhos de Transbordo Humano */}
          <div style={{ padding: '24px', backgroundColor: 'var(--bg-card-light)', border: '1.5px solid var(--border-rule)' }}>
            <div className="business-label" style={{ marginBottom: '8px' }}>
              GATILHOS DE TRANSBORDO AUTOMÁTICO
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '14px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={settings.pacing?.transbordo_pedido_humano}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      pacing: { ...settings.pacing!, transbordo_pedido_humano: e.target.checked },
                    })
                  }
                  style={{ accentColor: 'var(--blue-prime)' }}
                />
                <span>Solicitação direta de atendente humano</span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '14px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={settings.pacing?.transbordo_duvida_lgpd}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      pacing: { ...settings.pacing!, transbordo_duvida_lgpd: e.target.checked },
                    })
                  }
                  style={{ accentColor: 'var(--blue-prime)' }}
                />
                <span>Objeções complexas de LGPD ou segurança</span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '14px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={settings.pacing?.transbordo_desconto_alto}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      pacing: { ...settings.pacing!, transbordo_desconto_alto: e.target.checked },
                    })
                  }
                  style={{ accentColor: 'var(--blue-prime)' }}
                />
                <span>Pedido de desconto fora da alçada</span>
              </label>
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          4. SEÇÃO: CADÊNCIA DE FOLLOW-UP & HORÁRIO DE ATENDIMENTO
          ========================================================================= */}
      <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(440px, 1fr))', gap: '32px' }}>
        {/* Cadência de Follow-up */}
        <div className="business-card" style={{ padding: '36px' }}>
          <div className="business-label" style={{ color: 'var(--blue-prime)', marginBottom: '4px' }}>
            AUTOMAÇÃO TEMPORAL
          </div>
          <h2 className="business-title-large" style={{ marginBottom: '8px' }}>
            Regras de Cadência (Follow-up)
          </h2>
          <p style={{ fontSize: '15px', color: 'var(--text-muted)', marginBottom: '24px' }}>
            Esteira de reengajamento para leads que param de responder no meio da negociação.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <div className="business-label" style={{ marginBottom: '8px' }}>
                MÁXIMO DE TOQUES DE REENGAJAMENTO
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                {[1, 2, 3, 4, 5].map((toques) => {
                  const isSelected = settings.cadencia.max_tentativas === toques
                  return (
                    <button
                      key={toques}
                      type="button"
                      onClick={() =>
                        setSettings({
                          ...settings,
                          cadencia: { ...settings.cadencia, max_tentativas: toques },
                        })
                      }
                      className="btn-business"
                      style={{
                        flex: 1,
                        padding: '12px 0',
                        fontSize: '14px',
                        backgroundColor: isSelected ? 'var(--blue-prime)' : 'var(--bg-void)',
                        borderColor: isSelected ? 'var(--blue-prime)' : 'var(--border-rule)',
                        color: isSelected ? '#ffffff' : 'var(--text-muted)',
                      }}
                    >
                      {toques} {toques === 1 ? 'TOQUE' : 'TOQUES'}
                    </button>
                  )
                })}
              </div>
            </div>

            <div>
              <div className="business-label" style={{ marginBottom: '8px' }}>
                INTERVALO ENTRE DISPAROS (HORAS)
              </div>
              <input
                type="number"
                min={1}
                max={168}
                value={settings.cadencia.intervalo_horas}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    cadencia: { ...settings.cadencia, intervalo_horas: parseInt(e.target.value) || 24 },
                  })
                }
                className="input-business"
                style={{ fontSize: '18px', fontWeight: 800, fontFamily: 'var(--font-mono)' }}
              />
            </div>

            <div>
              <div className="business-label" style={{ marginBottom: '8px' }}>
                CALENDÁRIO DA CADÊNCIA
              </div>
              <button
                type="button"
                onClick={() =>
                  setSettings({
                    ...settings,
                    cadencia: { ...settings.cadencia, apenas_dias_uteis: !settings.cadencia.apenas_dias_uteis },
                  })
                }
                className="btn-business"
                style={{
                  width: '100%',
                  fontSize: '13px',
                  backgroundColor: settings.cadencia.apenas_dias_uteis ? 'var(--bg-void)' : 'var(--blue-surface)',
                  borderColor: settings.cadencia.apenas_dias_uteis ? 'var(--border-rule)' : 'var(--blue-prime)',
                  color: settings.cadencia.apenas_dias_uteis ? 'var(--text-muted)' : '#60a5fa',
                }}
              >
                {settings.cadencia.apenas_dias_uteis
                  ? 'APENAS DIAS ÚTEIS (PAUSAR FINS DE SEMANA)'
                  : '✓ INCLUIR FINS DE SEMANA (RESGATE CONTÍNUO 24/7)'}
              </button>
            </div>

            <div>
              <div className="business-label" style={{ marginBottom: '8px' }}>
                MENSAGEM DE ENCERRAMENTO POR INATIVIDADE
              </div>
              <textarea
                rows={3}
                value={settings.mensagem_inatividade}
                onChange={(e) =>
                  setSettings({
                    ...settings,
                    mensagem_inatividade: e.target.value,
                  })
                }
                className="input-business"
                style={{ fontSize: '14px', resize: 'vertical' }}
              />
            </div>
          </div>
        </div>

        {/* Janela de Atendimento e Horário Comercial */}
        <div className="business-card" style={{ padding: '36px' }}>
          <div className="business-label" style={{ color: 'var(--blue-prime)', marginBottom: '4px' }}>
            JANELA OPERACIONAL & ANTI-SPAM
          </div>
          <h2 className="business-title-large" style={{ marginBottom: '8px' }}>
            Horário de Funcionamento
          </h2>
          <p style={{ fontSize: '15px', color: 'var(--text-muted)', marginBottom: '24px' }}>
            Janela de tempo permitida para envios e proteções anti-bloqueio.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Toggle 24/7 Inbound */}
            <div>
              <div className="business-label" style={{ marginBottom: '8px' }}>
                MODO DE ATENDIMENTO RECEPTIVO
              </div>
              <button
                type="button"
                onClick={() =>
                  setSettings({
                    ...settings,
                    modo_24h_inbound: !settings.modo_24h_inbound,
                  })
                }
                className="btn-business"
                style={{
                  width: '100%',
                  fontSize: '13px',
                  backgroundColor: settings.modo_24h_inbound ? 'var(--blue-surface)' : 'var(--bg-void)',
                  borderColor: settings.modo_24h_inbound ? 'var(--blue-prime)' : 'var(--border-rule)',
                  color: settings.modo_24h_inbound ? '#60a5fa' : 'var(--text-muted)',
                }}
              >
                {settings.modo_24h_inbound ? '✓ ATENDIMENTO RECEPTIVO 24/7 ININTERRUPTO' : 'RESTRITO AO HORÁRIO COMERCIAL'}
              </button>
            </div>

            {/* Janela Comercial de Outbound */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div>
                <div className="business-label" style={{ marginBottom: '8px' }}>
                  INÍCIO EXPEDIENTE (0-23h)
                </div>
                <input
                  type="number"
                  min={0}
                  max={23}
                  value={settings.horario_comercial.inicio_hora}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      horario_comercial: { ...settings.horario_comercial, inicio_hora: parseInt(e.target.value) || 0 },
                    })
                  }
                  className="input-business"
                  style={{ fontSize: '18px', fontWeight: 800, fontFamily: 'var(--font-mono)' }}
                />
              </div>

              <div>
                <div className="business-label" style={{ marginBottom: '8px' }}>
                  TÉRMINO EXPEDIENTE (0-23h)
                </div>
                <input
                  type="number"
                  min={0}
                  max={23}
                  value={settings.horario_comercial.fim_hora}
                  onChange={(e) =>
                    setSettings({
                      ...settings,
                      horario_comercial: { ...settings.horario_comercial, fim_hora: parseInt(e.target.value) || 0 },
                    })
                  }
                  className="input-business"
                  style={{ fontSize: '18px', fontWeight: 800, fontFamily: 'var(--font-mono)' }}
                />
              </div>
            </div>

            {/* Dias da Semana */}
            <div>
              <div className="business-label" style={{ marginBottom: '10px' }}>
                DIAS DE ATIVIDADE
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                {DIAS_NOMES.map((nome, idx) => {
                  const ativo = settings.horario_comercial.dias_semana.includes(idx)
                  return (
                    <button
                      key={nome}
                      type="button"
                      onClick={() => toggleDiaSemana(idx)}
                      className="btn-business"
                      style={{
                        padding: '10px 4px',
                        fontSize: '12px',
                        backgroundColor: ativo ? 'var(--blue-surface)' : 'var(--bg-void)',
                        borderColor: ativo ? 'var(--blue-prime)' : 'var(--border-rule)',
                        color: ativo ? '#ffffff' : 'var(--text-muted)',
                      }}
                    >
                      {nome}
                    </button>
                  )
                })}
              </div>
            </div>

            <div>
              <div className="business-label" style={{ marginBottom: '8px' }}>
                FUSO HORÁRIO OFICIAL
              </div>
              <input
                type="text"
                disabled
                value={settings.horario_comercial.fuso_horario || 'America/Sao_Paulo (BRT - UTC-3)'}
                className="input-business"
                style={{ fontSize: '14px', color: 'var(--text-muted)', backgroundColor: 'var(--bg-void)' }}
              />
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          5. SEÇÃO: STATUS DAS INTEGRAÇÕES & CANAIS CONECTADOS
          ========================================================================= */}
      <section className="business-card" style={{ padding: '36px' }}>
        <div style={{ marginBottom: '24px', borderBottom: '1.5px solid var(--border-rule)', paddingBottom: '16px' }}>
          <div className="business-label" style={{ color: 'var(--blue-prime)', marginBottom: '4px' }}>
            CONEXÕES EXTERNAS & SEGURANÇA
          </div>
          <h2 className="business-title-large">
            Status das Integrações & Canais
          </h2>
          <p style={{ fontSize: '15px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Conexão com WhatsApp Gateway, CRM oficial e chave de autenticação para chamadas de API.
          </p>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '24px' }}>
          {/* Card WhatsApp Gateway */}
          <div style={{ padding: '24px', backgroundColor: 'var(--bg-card-light)', border: '1.5px solid var(--border-rule)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <div className="business-label">WHATSAPP GATEWAY</div>
              <span className="badge-brutalist badge-green">CONECTADO 🟢</span>
            </div>
            <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-headline)', fontFamily: 'var(--font-mono)' }}>
              {settings.integracoes?.whatsapp_numero || '+55 83 9192-3098'}
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '8px', lineHeight: 1.5 }}>
              Sessão Baileys ativa com reconexão automática e latência de 32ms.
            </div>
          </div>

          {/* Card CRM Ativo */}
          <div style={{ padding: '24px', backgroundColor: 'var(--bg-card-light)', border: '1.5px solid var(--border-rule)' }}>
            <div className="business-label" style={{ marginBottom: '12px' }}>
              CRM INTEGRADO
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              {(['KOMMO', 'HUBSPOT', 'RD_STATION', 'WEBHOOK'] as const).map((crm) => {
                const isSelected = settings.integracoes?.crm_ativo === crm
                return (
                  <button
                    key={crm}
                    type="button"
                    onClick={() =>
                      setSettings({
                        ...settings,
                        integracoes: { ...settings.integracoes!, crm_ativo: crm },
                      })
                    }
                    className="btn-business"
                    style={{
                      padding: '10px 4px',
                      fontSize: '11px',
                      backgroundColor: isSelected ? 'var(--blue-surface)' : 'var(--bg-void)',
                      borderColor: isSelected ? 'var(--blue-prime)' : 'var(--border-rule)',
                      color: isSelected ? '#60a5fa' : 'var(--text-muted)',
                    }}
                  >
                    {crm === 'KOMMO' ? 'KOMMO CRM' : crm}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Card API Key Master */}
          <div style={{ padding: '24px', backgroundColor: 'var(--bg-card-light)', border: '1.5px solid var(--border-rule)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <div className="business-label">CHAVE MASTER (X-API-KEY)</div>
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                style={{ background: 'none', border: 'none', color: '#60a5fa', fontSize: '12px', cursor: 'pointer', fontWeight: 800 }}
              >
                {showApiKey ? 'OCULTAR' : 'MOSTRAR'}
              </button>
            </div>
            <input
              type={showApiKey ? 'text' : 'password'}
              readOnly
              value={settings.integracoes?.api_key_master || 'master-secret-key-123'}
              className="input-business"
              style={{ fontSize: '14px', fontFamily: 'var(--font-mono)' }}
            />
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '8px' }}>
              Proteção das rotas de telemetria, auditoria e controle de transbordo.
            </div>
          </div>
        </div>
      </section>

      {/* =========================================================================
          6. SEÇÃO: ZONA DE CONTROLE CRÍTICO (EMERGENCY KILL-SWITCH)
          ========================================================================= */}
      <section
        style={{
          padding: '36px',
          backgroundColor: isSilenced ? 'rgba(255, 30, 70, 0.12)' : 'var(--bg-card)',
          border: '2px solid var(--red-prime)',
          position: 'relative',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '20px' }}>
          <div>
            <div className="business-label" style={{ color: 'var(--red-prime)', marginBottom: '4px' }}>
              ZONA DE SEGURANÇA OPERACIONAL // CONTROLE DE RISCO
            </div>
            <h2 className="business-title-large" style={{ color: '#ffffff' }}>
              Zona de Controle Crítico
            </h2>
            <p style={{ fontSize: '15px', color: 'var(--text-muted)', marginTop: '4px', maxWidth: '720px' }}>
              Caso a equipe humana precise assumir 100% dos diálogos de forma emergencial ou liberar filas de memória travadas.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap' }}>
            <button
              onClick={handleToggleKillSwitch}
              className={`btn-business ${isSilenced ? 'btn-business-blue' : 'btn-business-red'}`}
              style={{ padding: '16px 28px', fontSize: '14px' }}
            >
              {isSilenced ? '⚡ REATIVAR MOTOR DA IA' : '🛑 SILENCIAR TODAS AS RESPOSTAS DA IA'}
            </button>

            <button
              onClick={() => {
                setFeedback({ type: 'success', msg: 'BUFFERS E SESSÕES TEMPORÁRIAS DO REDIS LIMPOS COM SUCESSO.' })
                setTimeout(() => setFeedback(null), 3000)
              }}
              className="btn-business"
              style={{
                padding: '16px 24px',
                fontSize: '14px',
                borderColor: 'var(--red-border)',
                color: '#ff6b85',
              }}
            >
              🧹 LIMPAR FILAS DO REDIS
            </button>
          </div>
        </div>

        {isSilenced && (
          <div
            style={{
              marginTop: '20px',
              padding: '14px 20px',
              backgroundColor: 'rgba(255, 30, 70, 0.2)',
              border: '1px solid var(--red-prime)',
              color: '#ffffff',
              fontSize: '14px',
              fontWeight: 700,
            }}
          >
            ⚠️ ALERTA: O motor autônomo está silenciado globalmente. Nenhuma mensagem será disparada pelo Agente até que o motor seja reativado.
          </div>
        )}
      </section>
    </div>
  )
}
