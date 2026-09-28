"""
Implementação concreta do buffer de cache utilizando Redis.
Em conformidade com CacheBufferProtocol.
"""

from core.protocols import CacheBufferProtocol
from integrations.redis import buffer


class RedisBufferGateway:
    """Gateway de persistência temporária e debounce em cache Redis."""

    async def adicionar_mensagem(
        self,
        telefone: str,
        texto: str
    ) -> str:
        return await buffer.adicionar_mensagem(telefone, texto)

    async def obter_e_limpar_buffer(
        self,
        telefone: str
    ) -> list[str]:
        return await buffer.obter_e_limpar_buffer(telefone)

    async def verificar_se_e_ultima(
        self,
        telefone: str,
        token_disparado: str | float
    ) -> bool:
        return await buffer.verificar_se_e_ultima(telefone, token_disparado)


# Instância canônica singleton padrão
default_redis_buffer_gateway = RedisBufferGateway()
