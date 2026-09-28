"""
Camada de Serviços de Domínio e Aplicação (Pure Domain Services).
Centraliza estritamente as regras de negócio do Ecossistema de Vendas.
"""

from .inbound_service import InboundService
from .lead_service import LeadService
from .followup_service import FollowupService
from .transbordo_service import TransbordoService

__all__ = [
    "InboundService",
    "LeadService",
    "FollowupService",
    "TransbordoService",
]
