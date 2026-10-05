"""
Camada de Serviços de Domínio e Aplicação (Pure Domain Services).
Centraliza estritamente as regras de negócio do Ecossistema de Vendas.
"""

from .inbound_service import InboundService
from .lead_service import LeadService
from .followup_service import FollowupService
from .transbordo_service import TransbordoService
from .conversation_pacing_service import ConversationPacingService, PacingEvaluation, PacingLevel
from .optout_guard import OptOutGuard
from .inbound_failover_service import InboundFailoverService

__all__ = [
    "InboundService",
    "LeadService",
    "FollowupService",
    "TransbordoService",
    "ConversationPacingService",
    "PacingEvaluation",
    "PacingLevel",
    "OptOutGuard",
    "InboundFailoverService",
]


