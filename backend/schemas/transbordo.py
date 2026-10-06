"""
Esquemas Pydantic para Transbordo Humano Dinâmico e Painel de Atendimento.
"""

from typing import Optional
from pydantic import BaseModel, Field
from models import ControleAtendimento, EtapaFunil, TemperaturaLead


class TransbordoAssumirRequest(BaseModel):
    """Requisição para atendente humano assumir controle da conversa."""
    atendente: Optional[str] = "Especialista"


class TransbordoDevolverRequest(BaseModel):
    """Requisição para devolver controle da conversa ao piloto de IA."""
    diretriz_ia: Optional[str] = None
    etapa_sugerida: Optional[EtapaFunil] = None
    valor_estimado: Optional[float] = None


class TransbordoSolicitarRequest(BaseModel):
    """Requisição para escalar lead para transbordo manualmente via painel."""
    motivo: str = "Solicitação manual via painel"
    lead_vip: Optional[bool] = False


class MensagemHumanaManualRequest(BaseModel):
    """Payload de mensagem enviada manualmente pelo operador no painel."""
    texto: str
    atendente: Optional[str] = "Atendente"


class MensagemHumanaResponse(BaseModel):
    """Confirmação de envio de mensagem manual."""
    status: str
    interacao_id: int
    origem: str
    texto: str
    data: str


class TransbordoStatusResponse(BaseModel):
    """Status consolidado do controle de atendimento do lead."""
    lead_id: int
    nome: Optional[str] = None
    telefone: str
    controle: ControleAtendimento
    etapa_funil: EtapaFunil
    temperatura: TemperaturaLead
    valor_estimado: Optional[float] = None
    tags: list[str] = Field(default_factory=list)
    mensagem: str
