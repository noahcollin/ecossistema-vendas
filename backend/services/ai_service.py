import re
from typing import Optional, List, Any
from core.logger import logger
import models

from core.utils import higienizar_nome_perfil, PALAVRAS_BLOQUEADAS_NOME

async def gerar_resposta_vendedor(
    nome_cliente_bruto: str,
    interacoes: list,
    ficha_resumo: str | None = None,
    status_funil: models.LeadStatus | None = None
) -> str:
    """
    Fachada compatível que delega para o agente especializado de fechamento (sales_closer_agent).
    """
    from services.agents.sales_closer_agent import gerar_resposta_vendedor as _gerar
    return await _gerar(
        nome_cliente_bruto=nome_cliente_bruto,
        ficha_resumo=ficha_resumo,
        status_funil=status_funil,
        historico_recente=interacoes
    )

