"""
Serviço especializado na consolidação e normalização de mensagens multimídia de buffer (SRP).
Isola a responsabilidade de desempacotamento de mensagens acumuladas do Redis,
delegação para o pipeline de mídias e proteção contra estouro de contexto.
"""

import json
from typing import Optional
from core.logger import logger
from core.protocols import CacheBufferProtocol
from integrations.redis.gateway import default_redis_buffer_gateway
from integrations.media import normalizar_mensagem_para_texto
import schemas


class MessageConsolidator:
    """
    Consolidador de mensagens multimídia em lote (Debounce Buffer).
    Transforma payloads brutos enfileirados em texto coeso para processamento comercial.
    """

    def __init__(self, buffer_gateway: CacheBufferProtocol = default_redis_buffer_gateway) -> None:
        self.buffer_gateway = buffer_gateway

    async def consolidar_buffer(self, telefone: str, max_caracteres: int = 8000) -> Optional[str]:
        """
        Recupera as mensagens brutas do buffer, delega cada uma para normalização
        e retorna uma string consolidada e higienizada.
        """
        mensagens_raw = await self.buffer_gateway.obter_e_limpar_buffer(telefone)
        if not mensagens_raw:
            return None

        mensagens_processadas: list[str] = []
        for item in mensagens_raw:
            try:
                dados_item = json.loads(item) if (isinstance(item, str) and item.startswith("{")) else {"text": item}
                msg_obj = schemas.UazapiMessage(**dados_item)
                texto_mastigado = await normalizar_mensagem_para_texto(msg_obj)
                if texto_mastigado and texto_mastigado.strip():
                    mensagens_processadas.append(texto_mastigado.strip())
            except Exception as e:
                logger.error(f"[CONSOLIDATOR MEDIA ERRO] Falha ao normalizar item: {e}")
                if str(item).strip():
                    mensagens_processadas.append(str(item).strip())

        if not mensagens_processadas:
            return None

        texto_consolidado = "\n".join(mensagens_processadas)

        # 🛡️ Proteção contra estouro de contexto e payloads excessivos
        if len(texto_consolidado) > max_caracteres:
            logger.warning(
                f"[PAYLOAD GIGANTE] Mensagem de {telefone} truncada de {len(texto_consolidado)} "
                f"para {max_caracteres} caracteres."
            )
            texto_consolidado = (
                texto_consolidado[:max_caracteres]
                + "\n[... texto truncado por exceder o limite de segurança ...]"
            )

        logger.info(
            f"[CLIENTE] 🗨️ Mensagem Consolidada ({len(mensagens_processadas)} partes):\n{texto_consolidado}"
        )
        return texto_consolidado


# Instância padrão compartilhada
default_message_consolidator = MessageConsolidator()
