/**
 * Contratos de Configuração Operacional ("Sala de Máquinas") sincronizados com schemas/settings.py.
 */

export interface ProdutoItem {
  id: string;
  nome: string;
  descricao: string;
  modelo_comercial: string;
  qualificacao_minima: string;
  diretriz_venda: string;
  preco_base_mensal: number;
  taxa_setup: number;
  ativo: boolean;
}

export interface CadenciaConfig {
  max_tentativas: number;
  intervalo_horas: number;
  intervalos_toques: number[];
  apenas_dias_uteis: boolean;
  respeitar_horario_comercial: boolean;
}

export interface HorarioComercialConfig {
  inicio_hora: number;
  fim_hora: number;
  dias_semana: number[];
  fuso_horario: string;
}

export interface PacingConfig {
  delay_base_ms: number;
  intervalo_entre_baloes_seg: number;
  simular_digitacao: boolean;
  limiar_proativo: number;
  limiar_decisivo: number;
  limiar_max_finops: number;
}

export interface OperacaoSettings {
  produtos: ProdutoItem[];
  cadencia: CadenciaConfig;
  horario_comercial: HorarioComercialConfig;
  pacing: PacingConfig;
  debounce_segundos: number;
  modo_24h_inbound: boolean;
  ia_silenciada_global: boolean;
  mensagem_inatividade?: string | null;
  atualizado_em?: string | null;
}

export type OperacaoSettingsUpdate = Partial<Omit<OperacaoSettings, 'atualizado_em'>>;

export interface KillSwitchResponse {
  ia_silenciada_global: boolean;
  atualizado_em?: string | null;
  mensagem: string;
}

export interface RedisPurgeResponse {
  status: string;
  chaves_removidas: number;
  mensagem: string;
}
