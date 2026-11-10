import type { EtapaFunil, TemperaturaLead, TipoEntradaLead } from './telemetry';

export type TimeRange = '24h' | '7d' | '30d';

export interface FinanceiroKPIs {
  pipeline_ativo_reais: number;
  receita_ganha_reais: number;
  valor_perdido_reais: number;
  ticket_medio_reais: number;
  total_leads_ganhos: number;
  total_leads_perdidos: number;
  total_leads_em_andamento: number;
  taxa_conversao_pct: number;
}

export interface EtapaFunilDistribuicao {
  etapa: EtapaFunil;
  quantidade: number;
  valor_total_reais: number;
  percentual_base: number;
}

export interface TemperaturaDistribuicao {
  temperatura: TemperaturaLead;
  quantidade: number;
  percentual: number;
}

export interface FunilKPIs {
  por_etapa: EtapaFunilDistribuicao[];
  por_temperatura: TemperaturaDistribuicao[];
  leads_quentes_count: number;
}

export interface CanalOrigemItem {
  origem_canal: string;
  total_leads: number;
  leads_ganhos: number;
  receita_reais: number;
  taxa_conversao_pct: number;
}

export interface TipoEntradaItem {
  tipo_entrada: TipoEntradaLead;
  total_leads: number;
  leads_ganhos: number;
  receita_reais: number;
  taxa_conversao_pct: number;
}

export interface AquisicaoKPIs {
  por_canal: CanalOrigemItem[];
  por_tipo_entrada: TipoEntradaItem[];
  canal_campeao_receita?: string | null;
  canal_campeao_conversao?: string | null;
}

export interface MotivoPerdaItem {
  motivo: string;
  quantidade: number;
  valor_perdido_reais: number;
  percentual_do_total: number;
}

export interface PerdasKPIs {
  total_descartes: number;
  motivos_ranking: MotivoPerdaItem[];
  principal_motivo?: string | null;
}

export interface VolumeMensagensItem {
  total_mensagens: number;
  mensagens_clientes: number;
  mensagens_operacao: number;
}

export interface FollowupEficaciaKPIs {
  total_agendados: number;
  total_disparados: number;
  total_resgatados_por_resposta: number;
  total_congelados_cadencia: number;
  taxa_resgate_pct: number;
}

export interface ConversasKPIs {
  volume_mensagens: VolumeMensagensItem;
  eficacia_followup: FollowupEficaciaKPIs;
}

export interface DashboardOverviewResponse {
  gerado_em: string;
  total_leads_cadastrados: number;
  financeiro: FinanceiroKPIs;
  funil: FunilKPIs;
  aquisicao: AquisicaoKPIs;
  perdas: PerdasKPIs;
  conversas: ConversasKPIs;
}

export interface TractionPoint {
  label: string;
  entradas: number;
  fechamentos: number;
  capital: number;
}
