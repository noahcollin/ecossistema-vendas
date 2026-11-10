/**
 * Contratos de Domínio Estritos 1:1 com os Schemas Pydantic v2 do Backend.
 * Elimina drifts de enumeração (PROPOSTA_ENVIADA, EM_TRANSBORDO) e campos órfãos.
 */

export type EtapaFunil = 'NOVO_CONTATO' | 'QUALIFICACAO' | 'NEGOCIACAO' | 'FECHAMENTO';

export type DesfechoLead = 'EM_ANDAMENTO' | 'GANHO' | 'PERDIDO' | 'CONGELADO_CADENCIA';

export type ControleAtendimento = 'PILOTO_IA' | 'TRANSBORDO_SOLICITADO' | 'HUMANO_ASSUMIU';

export type TemperaturaLead = 'QUENTE' | 'MORNO' | 'FRIO';

export type TipoEntradaLead = 'INBOUND' | 'OUTBOUND';

export type InteracaoOrigem = 'cliente' | 'ia' | 'humano' | 'sistema';

export interface DadosQualificacao {
  segmento?: string | null;
  cargo_ou_papel?: string | null;
  tamanho_equipe?: string | null;
  cidade?: string | null;
  solucao_interesse?: string | null;
  dor_ou_necessidade?: string | null;
  gargalo_principal?: string | null;
  orcamento_estimado?: string | null;
  prazo_implementacao?: string | null;
  urgencia?: string | null;
  decisor?: boolean | null;
  ferramenta_atual?: string | null;
  volume_leads_mes?: string | null;
  objecoes_detectadas?: string[];
  contexto_extra?: string | null;
}

export interface DossieResultado {
  desfecho: DesfechoLead;
  motivo_raiz?: string | null;
  concorrente_citado?: string | null;
  diferencial_decisivo?: string | null;
}

export interface DossieProximoPasso {
  acao_sugerida: string;
  quando_retomar: string;
  dica_de_ouro: string;
}

export interface DossieComercial {
  historia_do_lead: string;
  o_que_agradou: string[];
  pontos_de_atrito_e_queixas: string[];
  resultado_final: DossieResultado;
  estrategia_utilizada: string;
  nota_atendimento_ia: number;
  feedback_para_o_negocio: string;
  proximo_passo: DossieProximoPasso;
  potencial_reativacao: 'ALTO' | 'MEDIO' | 'BAIXO' | 'NULO' | string;
  tipo_entrada?: string | null;
  origem_canal?: string | null;
}

export interface Lead {
  id: number;
  nome?: string | null;
  telefone: string;
  tipo_entrada: TipoEntradaLead;
  origem_canal: string;
  etapa_funil: EtapaFunil;
  desfecho: DesfechoLead;
  controle: ControleAtendimento;
  temperatura: TemperaturaLead;
  motivo_perda?: string | null;
  valor_estimado?: number | null;
  tags: string[];
  opt_out: boolean;
  resumo_perfil?: string | null;
  dados_qualificacao?: DadosQualificacao | null;
  dossie_comercial?: DossieComercial | null;
  criado_em: string;
}

export interface Interacao {
  id: number;
  origem: InteracaoOrigem;
  texto: string;
  data: string;
}

export interface FollowupAgendado {
  id: number;
  lead_id: number;
  etapa_funil: EtapaFunil;
  tentativa: number;
  agendado_para: string;
  status: 'PENDENTE' | 'DISPARADO' | 'CANCELADO_POR_RESPOSTA' | 'ABORTADO';
  mensagem_disparada?: string | null;
  criado_em: string;
  atualizado_em: string;
}

export interface SystemHealthResponse {
  status: 'healthy' | 'degraded' | 'offline';
  timestamp: string;
  ambiente?: string;
  gateway_whatsapp?: string;
  ia_silenciada_global?: boolean;
  modo_24h_inbound?: boolean;
  sandbox_mode?: boolean;
  buffers_pendentes?: number;
  tasks_ativas?: number;
  alerta_operacional?: string;
  latency_ms?: number;
  componentes: {
    postgres?: string;
    redis?: string;
    uazapi_token?: boolean;
    openai_key?: boolean;
    openai_creditos?: string;
  };
}
