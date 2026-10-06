"""
Contratos de Dados (DTOs Pydantic v2) para Analytics e Business Intelligence.
Estruturado em 5 blocos comerciais objetivos para alimentar o Dashboard Executivo.
"""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field

from models.enums import EtapaFunil, TemperaturaLead, TipoEntradaLead


# --- Bloco 1: Métricas Financeiras & Pipeline ---

class FinanceiroKPIs(BaseModel):
    """Indicadores consolidados de receita, pipeline e conversão comercial."""
    pipeline_ativo_reais: float = Field(0.0, description="Soma do valor estimado dos leads em andamento")
    receita_ganha_reais: float = Field(0.0, description="Soma do valor estimado dos leads com desfecho GANHO")
    valor_perdido_reais: float = Field(0.0, description="Soma do valor estimado dos leads com desfecho PERDIDO")
    ticket_medio_reais: float = Field(0.0, description="Média de receita por lead ganho")
    total_leads_ganhos: int = Field(0, description="Total de vendas concluídas")
    total_leads_perdidos: int = Field(0, description="Total de negociações perdidas")
    total_leads_em_andamento: int = Field(0, description="Total de negociações ativas no funil")
    taxa_conversao_pct: float = Field(0.0, description="Percentual de conversão sobre leads finalizados")


# --- Bloco 2: Saúde do Funil de Vendas ---

class EtapaFunilDistribuicao(BaseModel):
    """Distribuição de volume e valor em uma etapa específica do funil."""
    etapa: EtapaFunil
    quantidade: int = 0
    valor_total_reais: float = 0.0
    percentual_base: float = 0.0


class TemperaturaDistribuicao(BaseModel):
    """Termômetro de urgência e propensão de compra dos leads."""
    temperatura: TemperaturaLead
    quantidade: int = 0
    percentual: float = 0.0


class FunilKPIs(BaseModel):
    """Métricas de avanço no funil de vendas e priorização de leads."""
    por_etapa: List[EtapaFunilDistribuicao] = Field(default_factory=list)
    por_temperatura: List[TemperaturaDistribuicao] = Field(default_factory=list)
    leads_quentes_count: int = Field(0, description="Total de leads com temperatura QUENTE que demandam prioridade")


# --- Bloco 3: Aquisição & Performance de Canais ---

class CanalOrigemItem(BaseModel):
    """Performance consolidada de um canal específico de tráfego."""
    origem_canal: str
    total_leads: int = 0
    leads_ganhos: int = 0
    receita_reais: float = 0.0
    taxa_conversao_pct: float = 0.0


class TipoEntradaItem(BaseModel):
    """Performance comparativa entre Inbound e Outbound."""
    tipo_entrada: TipoEntradaLead
    total_leads: int = 0
    leads_ganhos: int = 0
    receita_reais: float = 0.0
    taxa_conversao_pct: float = 0.0


class AquisicaoKPIs(BaseModel):
    """Métricas de retorno e eficácia dos canais de captação."""
    por_canal: List[CanalOrigemItem] = Field(default_factory=list)
    por_tipo_entrada: List[TipoEntradaItem] = Field(default_factory=list)
    canal_campeao_receita: Optional[str] = Field(None, description="Canal que mais gerou receita faturada")
    canal_campeao_conversao: Optional[str] = Field(None, description="Canal com maior taxa de fechamento")


# --- Bloco 4: Inteligência de Perdas & Objeções ---

class MotivoPerdaItem(BaseModel):
    """Mapeamento semântico de motivos de descarte classificados pela IA."""
    motivo: str
    quantidade: int = 0
    valor_perdido_reais: float = 0.0
    percentual_do_total: float = 0.0


class PerdasKPIs(BaseModel):
    """Análise de Pareto de perdas e objeções não superadas."""
    total_descartes: int = 0
    motivos_ranking: List[MotivoPerdaItem] = Field(default_factory=list)
    principal_motivo: Optional[str] = Field(None, description="Objeção ou motivo que mais causou perdas")


# --- Bloco 5: Operação de Conversas & Eficácia do Follow-up ---

class VolumeMensagensItem(BaseModel):
    """Atividade conversacional no WhatsApp."""
    total_mensagens: int = 0
    mensagens_clientes: int = 0
    mensagens_operacao: int = 0


class FollowupEficaciaKPIs(BaseModel):
    """Rendimento e capacidade de resgate do motor de cadência temporal."""
    total_agendados: int = 0
    total_disparados: int = 0
    total_resgatados_por_resposta: int = Field(0, description="Leads que voltaram a responder após toque de follow-up")
    total_congelados_cadencia: int = Field(0, description="Leads que esgotaram 3 toques sem retorno")
    taxa_resgate_pct: float = Field(0.0, description="Percentual de follow-ups que recuperaram o cliente sumido")


class ConversasKPIs(BaseModel):
    """Métricas combinadas de engajamento no WhatsApp e reativações."""
    volume_mensagens: VolumeMensagensItem = Field(default_factory=VolumeMensagensItem)
    eficacia_followup: FollowupEficaciaKPIs = Field(default_factory=FollowupEficaciaKPIs)


# --- Resposta Consolidada para a Home do Dashboard ---

class DashboardOverviewResponse(BaseModel):
    """
    Agregador executivo para a tela principal do Dashboard.
    Retorna os 5 blocos em uma única requisição veloz.
    """
    gerado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    total_leads_cadastrados: int = 0
    financeiro: FinanceiroKPIs = Field(default_factory=FinanceiroKPIs)
    funil: FunilKPIs = Field(default_factory=FunilKPIs)
    aquisicao: AquisicaoKPIs = Field(default_factory=AquisicaoKPIs)
    perdas: PerdasKPIs = Field(default_factory=PerdasKPIs)
    conversas: ConversasKPIs = Field(default_factory=ConversasKPIs)
