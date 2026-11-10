"""
Subpacote de Serviços Inbound.
Exporta o orquestrador InboundService, WebhookApplicationService, consolidadores, guardião de opt-out e failover.
"""

from services.inbound.orchestrator import InboundService
from services.inbound.webhook_service import WebhookApplicationService
from services.inbound.send_event_service import SendEventService
from services.inbound.consolidation import MessageConsolidator, default_message_consolidator
from services.inbound.optout import OptOutGuard
from services.inbound.failover import InboundFailoverService

__all__ = [
    "InboundService",
    "WebhookApplicationService",
    "SendEventService",
    "MessageConsolidator",
    "default_message_consolidator",
    "OptOutGuard",
    "InboundFailoverService",
]
