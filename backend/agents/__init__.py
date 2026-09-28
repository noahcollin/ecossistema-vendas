"""
Módulo de Agentes Especializados do Ecossistema de Vendas.
Separação de papéis:
- lead_analyzer_agent: Analista de Perfil, Memória e Máquina de Estados (FSM)
- sales_closer_agent: Vendedor Consultivo Frontline ('Seu Zé')
"""

from .lead_analyzer_agent import analisar_lead_e_fsm
from .sales_closer_agent import gerar_resposta_vendedor, gerar_mensagem_followup
from .deal_auditor_agent import auditar_jornada_lead
from .prompts import (
    PROMPT_BASE_VENDEDOR,
    ORIENTACOES_POR_ESTAGIO,
    ORIENTACOES_FOLLOWUP,
    PROMPT_SISTEMA_ANALISTA,
    PROMPT_SISTEMA_AUDITOR
)

__all__ = [
    "analisar_lead_e_fsm",
    "gerar_resposta_vendedor",
    "gerar_mensagem_followup",
    "auditar_jornada_lead",
    "PROMPT_BASE_VENDEDOR",
    "ORIENTACOES_POR_ESTAGIO",
    "ORIENTACOES_FOLLOWUP",
    "PROMPT_SISTEMA_ANALISTA",
    "PROMPT_SISTEMA_AUDITOR"
]
