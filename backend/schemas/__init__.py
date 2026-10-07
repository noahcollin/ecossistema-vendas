"""
Módulo Centralizador e Modular de Esquemas Pydantic v2 do Ecossistema de Vendas.
Re-exporta todos os esquemas garantindo compatibilidade total com os imports existentes.
"""

from models import (
    EtapaFunil,
    DesfechoLead,
    ControleAtendimento,
    TemperaturaLead,
    TipoEntradaLead,
    StatusFollowup,
    InteracaoOrigem,
)
from .lead import (
    DadosQualificacao,
    LeadCreate,
    LeadResponse,
    InteracaoResponse,
)
from .fsm import (
    LeadAnalysisOutput,
)
from .auditor import (
    DossieResultado,
    DossieProximoPasso,
    DossieComercialOutput,
)
from .followup import (
    FollowupAgendadoResponse,
)
from .transbordo import (
    TransbordoAssumirRequest,
    TransbordoDevolverRequest,
    TransbordoSolicitarRequest,
    MensagemHumanaManualRequest,
    MensagemHumanaResponse,
    TransbordoStatusResponse,
)
from .uazapi import (
    UazapiChat,
    UazapiMessage,
    UazapiPayload,
)
from .analytics import (
    FinanceiroKPIs,
    EtapaFunilDistribuicao,
    TemperaturaDistribuicao,
    FunilKPIs,
    CanalOrigemItem,
    TipoEntradaItem,
    AquisicaoKPIs,
    MotivoPerdaItem,
    PerdasKPIs,
    VolumeMensagensItem,
    FollowupEficaciaKPIs,
    ConversasKPIs,
    DashboardOverviewResponse,
)
from .settings import (
    ProdutoItem,
    CadenciaConfig,
    HorarioComercialConfig,
    OperacaoSettingsResponse,
    OperacaoSettingsUpdate,
)

__all__ = [
    # Enums
    "EtapaFunil",
    "DesfechoLead",
    "ControleAtendimento",
    "TemperaturaLead",
    "TipoEntradaLead",
    "StatusFollowup",
    "InteracaoOrigem",
    # Lead & Interação
    "DadosQualificacao",
    "LeadCreate",
    "LeadResponse",
    "InteracaoResponse",
    # FSM & Auditoria
    "LeadAnalysisOutput",
    "DossieResultado",
    "DossieProximoPasso",
    "DossieComercialOutput",
    # Follow-up
    "FollowupAgendadoResponse",
    # Transbordo
    "TransbordoAssumirRequest",
    "TransbordoDevolverRequest",
    "TransbordoSolicitarRequest",
    "MensagemHumanaManualRequest",
    "MensagemHumanaResponse",
    "TransbordoStatusResponse",
    # Uazapi
    "UazapiChat",
    "UazapiMessage",
    "UazapiPayload",
    # Analytics & Dashboard
    "FinanceiroKPIs",
    "EtapaFunilDistribuicao",
    "TemperaturaDistribuicao",
    "FunilKPIs",
    "CanalOrigemItem",
    "TipoEntradaItem",
    "AquisicaoKPIs",
    "MotivoPerdaItem",
    "PerdasKPIs",
    "VolumeMensagensItem",
    "FollowupEficaciaKPIs",
    "ConversasKPIs",
    "DashboardOverviewResponse",
    # Settings & Customizações da Operação
    "ProdutoItem",
    "CadenciaConfig",
    "HorarioComercialConfig",
    "OperacaoSettingsResponse",
    "OperacaoSettingsUpdate",
]

