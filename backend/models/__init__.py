"""
Módulo Centralizador e Modular de Modelos ORM e Enums do Domínio.
Re-exporta todas as entidades para manter compatibilidade absoluta de imports.
"""

from core.database import Base
from .enums import (
    EtapaFunil,
    DesfechoLead,
    ControleAtendimento,
    TemperaturaLead,
    TipoEntradaLead,
    InteracaoOrigem,
    StatusFollowup,
)
from .lead import Lead
from .interaction import Interacao
from .followup import FollowupAgendado
from .settings import ConfiguracaoOperacional

__all__ = [
    "Base",
    "EtapaFunil",
    "DesfechoLead",
    "ControleAtendimento",
    "TemperaturaLead",
    "TipoEntradaLead",
    "InteracaoOrigem",
    "StatusFollowup",
    "Lead",
    "Interacao",
    "FollowupAgendado",
    "ConfiguracaoOperacional",
]
