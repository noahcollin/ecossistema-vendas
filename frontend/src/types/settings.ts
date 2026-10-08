export interface ProdutoItem {
  id: string
  nome: string
  descricao: string
  preco_base_mensal: number
  taxa_setup: number
  ativo: boolean
}

export interface CadenciaConfig {
  max_tentativas: number
  intervalo_horas: number
  apenas_dias_uteis: boolean
  respeitar_horario_comercial: boolean
}

export interface HorarioComercialConfig {
  inicio_hora: number
  fim_hora: number
  dias_semana: number[]
  fuso_horario: string
}

export interface PacingConfig {
  quebra_baloes_ativa: boolean
  transbordo_pedido_humano: boolean
  transbordo_duvida_lgpd: boolean
  transbordo_desconto_alto: boolean
}

export interface IntegracoesConfig {
  crm_ativo: 'KOMMO' | 'HUBSPOT' | 'RD_STATION' | 'WEBHOOK'
  whatsapp_conectado: boolean
  whatsapp_numero: string
  api_key_master: string
}

export interface OperacaoSettings {
  produtos: ProdutoItem[]
  cadencia: CadenciaConfig
  horario_comercial: HorarioComercialConfig
  debounce_segundos: number
  mensagem_inatividade: string
  modo_24h_inbound?: boolean
  ia_silenciada_global?: boolean
  pacing?: PacingConfig
  integracoes?: IntegracoesConfig
  atualizado_em?: string | null
}
