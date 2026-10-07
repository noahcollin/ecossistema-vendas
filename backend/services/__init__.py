"""
Camada de Serviços de Domínio e Aplicação (Domain-Driven Architecture).
Organizada em subpacotes coesos por contexto delimitado (Bounded Context):
- services.inbound: orquestração da recepção de mensagens, consolidação, opt-out e failover.
- services.cadence: motor de cadência temporal e follow-ups inteligentes.
- services.pacing: velocidade conversacional e guardrails anti-loop (FinOps).
- services.lead: ciclo de vida, memórias de longo prazo e auditoria do lead.
- services.handover: transbordo humano, reversão automática por timeout e cockpit.
"""

import sys

# Subpacotes canônicos
from . import inbound
from . import cadence
from . import pacing
from . import lead
from . import handover
from . import settings

# Classes e instâncias exportadas na fachada
from .inbound import (
    InboundService,
    MessageConsolidator,
    default_message_consolidator,
    OptOutGuard,
    InboundFailoverService,
)
from .cadence import FollowupService
from .pacing import (
    ConversationPacingService,
    PacingEvaluation,
    PacingLevel,
)
from .lead import LeadService, AnalyticsService
from .handover import (
    TransbordoService,
    DashboardService,
)
from .settings import SettingsService

# Módulos concretos para injeção de retrocompatibilidade dinâmica no sys.modules (Zero Ghost Files)
from .inbound import orchestrator as _inbound_orchestrator
from .inbound import consolidation as _inbound_consolidation
from .inbound import optout as _inbound_optout
from .inbound import failover as _inbound_failover
from .cadence import followup_service as _cadence_followup
from .pacing import pacing_service as _pacing_impl
from .lead import lead_service as _lead_impl
from .handover import transbordo_service as _handover_transbordo
from .settings import settings_service as _settings_impl

# Aliases dinâmicos transparentes: suporta 'from services.transbordo_service import TransbordoService' e 'getattr(services, "transbordo_service")'
inbound_service = _inbound_orchestrator
message_consolidation = _inbound_consolidation
optout_guard = _inbound_optout
inbound_failover_service = _inbound_failover
followup_service = _cadence_followup
conversation_pacing_service = _pacing_impl
lead_service = _lead_impl
transbordo_service = _handover_transbordo
settings_service = _settings_impl

sys.modules["services.inbound_service"] = _inbound_orchestrator
sys.modules["services.message_consolidation"] = _inbound_consolidation
sys.modules["services.optout_guard"] = _inbound_optout
sys.modules["services.inbound_failover_service"] = _inbound_failover
sys.modules["services.followup_service"] = _cadence_followup
sys.modules["services.conversation_pacing_service"] = _pacing_impl
sys.modules["services.lead_service"] = _lead_impl
sys.modules["services.transbordo_service"] = _handover_transbordo
sys.modules["services.settings_service"] = _settings_impl

__all__ = [
    # Subpacotes
    "inbound",
    "cadence",
    "pacing",
    "lead",
    "handover",
    "settings",
    # Serviços Inbound
    "InboundService",
    "MessageConsolidator",
    "default_message_consolidator",
    "OptOutGuard",
    "InboundFailoverService",
    # Serviços Cadence
    "FollowupService",
    # Serviços Pacing
    "ConversationPacingService",
    "PacingEvaluation",
    "PacingLevel",
    # Serviços Lead
    "LeadService",
    "AnalyticsService",
    # Serviços Handover
    "TransbordoService",
    "DashboardService",
    # Serviços Settings
    "SettingsService",
]
