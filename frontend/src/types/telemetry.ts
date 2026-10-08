export interface LeadInteraction {
  id: number
  origem: 'cliente' | 'ia' | 'humano' | 'sistema'
  texto: string
  data?: string
  criado_em?: string | null
}

export interface DossieProximoPasso {
  acao_sugerida: string
  quando_retomar?: string | null
  dica_de_ouro: string
}

export interface DossieResultado {
  desfecho: string
  motivo_raiz?: string | null
  concorrente_citado?: string | null
  diferencial_decisivo?: string | null
}

export interface LeadDossie {
  resumo_executivo?: string
  historia_do_lead?: string
  win_loss_analise?: string
  dica_de_ouro?: string
  perfil_cliente?: string
  consumo_estimado?: string
  objecoes_mapeadas?: string[]
  o_que_agradou?: string[]
  pontos_de_atrito_e_queixas?: string[]
  resultado_final?: DossieResultado
  estrategia_utilizada?: string
  nota_atendimento_ia?: number
  feedback_para_o_negocio?: string
  proximo_passo?: DossieProximoPasso
  potencial_reativacao?: string
}

export interface LeadItem {
  id: number
  telefone: string
  nome: string
  tipo_entrada?: string
  origem_canal?: string
  etapa_funil: string
  desfecho: string
  controle: string
  temperatura?: string
  motivo_perda?: string | null
  valor_estimado?: number | null
  tags: string[]
  resumo_perfil?: string | null
  dados_qualificacao?: Record<string, any> | null
  criado_em: string
  atualizado_em?: string
  dossie_comercial?: LeadDossie | null
}

export interface TelemetryKpi {
  totalLeads: number
  taxaConversao: number
  leadsAtivosIa: number
  transbordosPendentes: number
  volumeNegociacao: number
  tempoMedioResposta: string
}

export interface FunnelMetric {
  etapa: string
  total: number
  ia: number
  humano: number
}
