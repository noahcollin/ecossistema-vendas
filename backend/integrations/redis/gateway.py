"""
Implementação concreta do buffer de cache utilizando Redis.
Em conformidade estrita com CacheBufferProtocol.
"""

from integrations.redis import buffer


class RedisBufferGateway:
    """Gateway de persistência temporária, locks distribuídos e debounce em cache Redis."""

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

    async def listar_telefones_com_buffer(self) -> list[str]:
        return await buffer.listar_telefones_com_buffer()

    async def contar_buffers_pendentes(self) -> int:
        return await buffer.contar_buffers_pendentes()

    async def registrar_marcador_bot(
        self,
        msg_id: str,
        ttl_segundos: int = 120
    ) -> None:
        await buffer.registrar_marcador_bot(msg_id, ttl_segundos=ttl_segundos)

    async def verificar_marcador_bot(self, msg_id: str) -> bool:
        return await buffer.verificar_marcador_bot(msg_id)

    async def adquirir_lock(
        self,
        chave: str,
        ttl_segundos: int = 45
    ) -> str | None:
        return await buffer.adquirir_lock(chave, ttl_segundos=ttl_segundos)

    async def liberar_lock(
        self,
        chave: str,
        token: str
    ) -> bool:
        return await buffer.liberar_lock(chave, token)

    async def expurgar_filas_volateis(self) -> int:
        return await buffer.expurgar_filas_volateis()


# Instância canônica singleton padrão
default_redis_buffer_gateway = RedisBufferGateway()
