"""
Módulo Centralizador e Modular de Prompts dos Agentes.
Reúne e exporta as personas e diretrizes de cada agente cognitivo.
"""

from .closer_vendedor import (
    PROMPT_BASE_VENDEDOR as PROMPT_BASE_VENDEDOR,
    ORIENTACOES_POR_ESTAGIO as ORIENTACOES_POR_ESTAGIO,
)
from .followup import (
    ORIENTACOES_FOLLOWUP as ORIENTACOES_FOLLOWUP,
)
from .analista import (
    PROMPT_SISTEMA_ANALISTA as PROMPT_SISTEMA_ANALISTA,
)
from .auditor import (
    PROMPT_SISTEMA_AUDITOR as PROMPT_SISTEMA_AUDITOR,
)

__all__ = [
    "PROMPT_BASE_VENDEDOR",
    "ORIENTACOES_POR_ESTAGIO",
    "ORIENTACOES_FOLLOWUP",
    "PROMPT_SISTEMA_ANALISTA",
    "PROMPT_SISTEMA_AUDITOR",
]
