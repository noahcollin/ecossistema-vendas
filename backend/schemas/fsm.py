"""
Esquema de saída estruturada do Agente Analista e Supervisor de Funil (FSM).
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from models import EtapaFunil, DesfechoLead, TemperaturaLead
from .lead import DadosQualificacao


class LeadAnalysisOutput(BaseModel):
    """Diagnóstico cognitivo, classificação de etapas, tags e intenções pelo Analista."""
    model_config = ConfigDict(extra="forbid")

    resumo_perfil: str  # Resumo narrativo conciso do lead (perfil, dores, necessidades)
    etapa_sugerida: EtapaFunil  # Etapa na esteira de vendas (NOVO_CONTATO, QUALIFICACAO, NEGOCIACAO, FECHAMENTO)
    desfecho_sugerido: DesfechoLead  # Saúde da negociação (EM_ANDAMENTO, GANHO, PERDIDO, CONGELADO_CADENCIA)
    transbordo_sugerido: bool  # True se o lead pediu atendente humano, agressividade ou exceção crítica
    temperatura_sugerida: TemperaturaLead  # Nível de urgência/interesse (FRIO, MORNO, QUENTE)
    origem_canal_detectada: Optional[str] = None  # Origem identificada (META_ADS, GOOGLE_SEARCH, SITE_LANDING_PAGE, INDICACAO, etc.)
    motivo_perda: Optional[str] = None  # Termo curto (1 a 3 palavras) se desfecho for PERDIDO
    valor_estimado: Optional[float] = None  # Valor financeiro do deal/orçamento/fatura se mencionado
    tags_sugeridas: list[str] = Field(default_factory=list)  # Tags comportamentais
    opt_out_detectado: bool = False  # True se o cliente pediu remoção/LGPD (pare, não mande mensagem)
    justificativa: str  # Justificativa da decisão analítica
    dados_qualificacao: DadosQualificacao  # Atributos estruturados do nicho
