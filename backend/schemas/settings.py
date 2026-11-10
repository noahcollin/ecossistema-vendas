"""
Esquemas Pydantic v2 para Configurações Operacionais Dinâmicas do Ecossistema.
Contratos de dados para customização de catálogo de produtos, preços, pacing,
regras de cadência, horários comerciais e governança (Kill-Switch / Expurgo Redis).
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
    modelo_comercial: str = Field(default="MRR + Setup", description="Modelo de cobrança (ex: 'SaaS Recorrente', 'Setup + Mensal')")
    qualificacao_minima: str = Field(default="", description="Critério mínimo de qualificação (ex: 'Equipe >= 3 vendedores')")
    diretriz_venda: str = Field(default="", description="Instrução tática específica para o Agente Closer")
    preco_base_mensal: float = Field(..., ge=0.0, description="Mensalidade base em R$")
    taxa_setup: float = Field(default=0.0, ge=0.0, description="Taxa de implementação/setup em R$")
    ativo: bool = Field(default=True, description="Se a solução está ativa para oferta")


class CadenciaConfig(BaseModel):
    """Regras de follow-up do motor de cadência temporal."""
    model_config = ConfigDict(extra="ignore")

    max_tentativas: int = Field(default=3, ge=1, le=7, description="Número máximo de toques (1 a 7)")
    intervalo_horas: int = Field(default=6, ge=1, le=168, description="Intervalo padrão/fallback entre toques em horas")
    intervalos_toques: List[float] = Field(
        default_factory=lambda: [2.0, 6.0, 12.0],
        description="Intervalos progressivos por toque em horas dentro da janela de 24h da Meta (ex: [2.0, 6.0, 12.0])"
    )
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


class PacingConfig(BaseModel):
    """Parâmetros de humanização, ritmo conversacional e trava FinOps anti-loop."""
    model_config = ConfigDict(extra="ignore")

    delay_base_ms: int = Field(default=1500, ge=250, le=10000, description="Delay base de digitação antes do envio (ms)")
    intervalo_entre_baloes_seg: float = Field(default=1.8, ge=0.5, le=10.0, description="Pausa entre balões fatiados (s)")
    simular_digitacao: bool = Field(default=True, description="Enviar presença 'composing' antes dos balões")
    limiar_proativo: int = Field(default=10, ge=4, le=40, description="Interações até postura ativa de fechamento")
    limiar_decisivo: int = Field(default=20, ge=8, le=60, description="Interações até chamada conclusiva")
    limiar_max_finops: int = Field(default=30, ge=12, le=100, description="Trava máxima FinOps de encerramento cordial")


class OperacaoSettingsResponse(BaseModel):
    """Payload completo das configurações da operação retornado para o Dashboard."""
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    produtos: List[ProdutoItem]
    cadencia: CadenciaConfig
    horario_comercial: HorarioComercialConfig
    pacing: PacingConfig = Field(default_factory=PacingConfig)
    debounce_segundos: float = Field(default=8.0, ge=1.0, le=15.0, description="Janela de agrupamento de mensagens")
    modo_24h_inbound: bool = Field(default=True, description="Se True, responde leads receptivos 24/7; se False, respeita janela comercial")
    ia_silenciada_global: bool = Field(default=False, description="Kill-Switch global: silencia respostas autônomas e follow-ups")
    mensagem_inatividade: Optional[str] = Field(
        default="Olá! Notei que não conseguimos avançar no momento. Ficamos à disposição quando fizer sentido para você!",
        description="Mensagem enviada no encerramento por estagnação"
    )
    atualizado_em: Optional[datetime] = None


class OperacaoSettingsUpdate(BaseModel):
    """Payload para atualização parcial das configurações da operação via Dashboard."""
    model_config = ConfigDict(extra="ignore")

    produtos: Optional[List[ProdutoItem]] = None
    cadencia: Optional[CadenciaConfig] = None
    horario_comercial: Optional[HorarioComercialConfig] = None
    pacing: Optional[PacingConfig] = None
    debounce_segundos: Optional[float] = Field(default=None, ge=1.0, le=15.0)
    modo_24h_inbound: Optional[bool] = None
    ia_silenciada_global: Optional[bool] = None
    mensagem_inatividade: Optional[str] = None


class KillSwitchRequest(BaseModel):
    """Payload para alternância imediata do Kill-Switch global da IA."""
    silenciar: bool = Field(..., description="True para pausar toda a IA autônoma; False para retomar operação normal")


class KillSwitchResponse(BaseModel):
    """Confirmação de estado do Kill-Switch global."""
    ia_silenciada_global: bool
    atualizado_em: Optional[datetime] = None
    mensagem: str


class RedisPurgeResponse(BaseModel):
    """Resultado do expurgo não-bloqueante das filas voláteis do Redis."""
    status: str
    chaves_removidas: int
    mensagem: str
