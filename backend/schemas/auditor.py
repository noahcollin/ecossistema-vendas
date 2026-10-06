"""
Esquemas Pydantic para o Agente Auditor de Negócios e Dossiê Comercial.
"""

from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from models import DesfechoLead


class DossieResultado(BaseModel):
    """Diagnóstico do resultado comercial e causa raiz."""
    model_config = ConfigDict(extra="forbid")

    desfecho: DesfechoLead
    motivo_raiz: Optional[str] = None
    concorrente_citado: Optional[str] = None
    diferencial_decisivo: Optional[str] = None


class DossieProximoPasso(BaseModel):
    """Diretrizes de follow-up e ação humana pós-auditoria."""
    model_config = ConfigDict(extra="forbid")

    acao_sugerida: str
    quando_retomar: Optional[str] = None
    dica_de_ouro: str


class DossieComercialOutput(BaseModel):
    """Dossiê executivo completo para a liderança e equipe de vendas."""
    model_config = ConfigDict(extra="forbid")

    historia_do_lead: str
    o_que_agradou: list[str] = Field(default_factory=list)
    pontos_de_atrito_e_queixas: list[str] = Field(default_factory=list)
    resultado_final: DossieResultado
    estrategia_utilizada: str
    nota_atendimento_ia: float
    feedback_para_o_negocio: str
    proximo_passo: DossieProximoPasso
    potencial_reativacao: str  # "ALTO", "MEDIO", "BAIXO"
    tipo_entrada: Optional[str] = None
    origem_canal: Optional[str] = None
