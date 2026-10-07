"""
Esquemas Pydantic v2 para Configurações Operacionais Dinâmicas do Ecossistema.
Contratos de dados para customização de catálogo de produtos, preços,
regras de cadência e horários comerciais via Dashboard.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class ProdutoItem(BaseModel):
    """Item do catálogo de produtos e soluções comercializadas pela IA."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Identificador único (ex: 'agente_whatsapp')")
    nome: str = Field(..., description="Nome comercial da solução")
    descricao: str = Field(default="", description="Breve descrição da proposta de valor")
    preco_base_mensal: float = Field(..., ge=0.0, description="Mensalidade base em R$")
    taxa_setup: float = Field(default=0.0, ge=0.0, description="Taxa de implementação/setup em R$")
    ativo: bool = Field(default=True, description="Se a solução está ativa para oferta")


class CadenciaConfig(BaseModel):
    """Regras de follow-up do motor de cadência temporal."""
    model_config = ConfigDict(extra="ignore")

    max_tentativas: int = Field(default=3, ge=1, le=7, description="Número máximo de toques (1 a 7)")
    intervalo_horas: int = Field(default=24, ge=1, le=168, description="Intervalo padrão entre toques em horas")
    apenas_dias_uteis: bool = Field(default=True, description="Evitar disparos automáticos nos finais de semana")
    respeitar_horario_comercial: bool = Field(default=True, description="Disparar apenas na janela comercial permitida")


class HorarioComercialConfig(BaseModel):
    """Parâmetros de janela de atendimento e anti-ban."""
    model_config = ConfigDict(extra="ignore")

    inicio_hora: int = Field(default=8, ge=0, le=23, description="Hora de início (0-23)")
    fim_hora: int = Field(default=18, ge=0, le=23, description="Hora de término (0-23)")
    dias_semana: List[int] = Field(
        default_factory=lambda: [0, 1, 2, 3, 4],
        description="Dias de atendimento ativo: 0=Segunda, 4=Sexta, 5=Sábado, 6=Domingo"
    )
    fuso_horario: str = Field(default="America/Sao_Paulo", description="Fuso horário oficial da operação")


class OperacaoSettingsResponse(BaseModel):
    """Payload completo das configurações da operação retornado para o Dashboard."""
    model_config = ConfigDict(from_attributes=True)

    produtos: List[ProdutoItem]
    cadencia: CadenciaConfig
    horario_comercial: HorarioComercialConfig
    debounce_segundos: float = Field(default=4.5, ge=1.0, le=15.0, description="Janela de agrupamento de mensagens")
    mensagem_inatividade: Optional[str] = Field(
        default="Olá! Notei que não conseguimos avançar no momento. Ficamos à disposição quando fizer sentido para você!",
        description="Mensagem enviada no encerramento por estagnação"
    )
    atualizado_em: Optional[datetime] = None


class OperacaoSettingsUpdate(BaseModel):
    """Payload para atualização das configurações da operação via Dashboard."""
    model_config = ConfigDict(extra="ignore")

    produtos: Optional[List[ProdutoItem]] = None
    cadencia: Optional[CadenciaConfig] = None
    horario_comercial: Optional[HorarioComercialConfig] = None
    debounce_segundos: Optional[float] = Field(default=None, ge=1.0, le=15.0)
    mensagem_inatividade: Optional[str] = None
