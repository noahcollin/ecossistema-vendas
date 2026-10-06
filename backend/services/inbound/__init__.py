"""
Subpacote de Serviços Inbound.
Exporta o orquestrador InboundService, consolidadores, guardião de opt-out e failover.
"""

from services.inbound.orchestrator import InboundService
from services.inbound.consolidation import MessageConsolidator, default_message_consolidator
from services.inbound.optout import OptOutGuard
from services.inbound.failover import InboundFailoverService

__all__ = [
    "InboundService",
    "MessageConsolidator",
    "default_message_consolidator",
    "OptOutGuard",
    "InboundFailoverService",
]
