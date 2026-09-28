import time
from redis import asyncio as aioredis
from core.logger import logger
from core.config import settings

from core.exceptions import BufferOperationError

# Pool de conexão assíncrona global para o Redis
redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

# Script Lua atômico: garante que nenhuma mensagem seja perdida entre LRANGE e DEL
LUA_OBTER_E_LIMPAR = """
local msgs = redis.call('LRANGE', KEYS[1], 0, -1)
redis.call('DEL', KEYS[1])
redis.call('DEL', KEYS[2])
return msgs
"""

async def adicionar_mensagem(telefone: str, texto: str) -> str:
    """
    Enfileira o fragmento de mensagem no buffer do lead no Redis
    e atualiza o carimbo de data/hora (timestamp) atômico em nanossegundos.
    Retorna o token/carimbo único gerado.
    """
    try:
        token_tempo = str(time.time_ns())
        chave_buffer = f"buffer:{telefone}"
        chave_tempo = f"last_msg_time:{telefone}"
        
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.rpush(chave_buffer, texto)
            pipe.set(chave_tempo, token_tempo)
            pipe.expire(chave_buffer, 600)
            pipe.expire(chave_tempo, 600)
            await pipe.execute()
            
        logger.info(f"[BUFFER] 📥 Mensagem de {telefone} enfileirada no Redis. Token: {token_tempo}")
        return token_tempo
    except Exception as e:
        logger.error(f"[BUFFER ERRO] Falha ao adicionar mensagem no Redis: {e}")
        return str(time.time_ns())

async def verificar_se_e_ultima(telefone: str, token_disparado: str | float) -> bool:
    """
    Verifica se o token gravado no Redis ainda coincide com o token
    desta tarefa. Se outra mensagem tiver chegado no intervalo, retorna False.
    """
    try:
        chave_tempo = f"last_msg_time:{telefone}"
        ultimo_tempo = await redis_client.get(chave_tempo)
        
        if not ultimo_tempo:
            return False
            
        token_str = str(token_disparado).strip()
        ultimo_tempo_str = str(ultimo_tempo).strip()
        if ultimo_tempo_str == token_str:
            return True
            
        try:
            # Se contiver ponto decimal (formato segundos unix legado), permite tolerância de ponto flutuante
            if "." in token_str or "." in ultimo_tempo_str:
                return abs(float(ultimo_tempo_str) - float(token_str)) < 0.0001
            # Para inteiros como nanosegundos (time_ns), igualdade estrita de strings já define se é a última
            return False
        except (ValueError, TypeError):
            return False
    except Exception as e:
        logger.error(f"[BUFFER ERRO] Falha ao verificar timestamp no Redis: {e}")
        return False

async def obter_e_limpar_buffer(telefone: str) -> list[str]:
    """
    Recupera todas as mensagens acumuladas no buffer do lead e limpa as chaves
    de forma estritamente ATÔMICA via script Lua, eliminando race conditions.
    """
    try:
        chave_buffer = f"buffer:{telefone}"
        chave_tempo = f"last_msg_time:{telefone}"
        
        mensagens = await redis_client.eval(LUA_OBTER_E_LIMPAR, 2, chave_buffer, chave_tempo)
        logger.info(f"[BUFFER] 📦 {len(mensagens or [])} mensagens consolidadas e retiradas atomicamente de {telefone}")
        return mensagens or []
    except Exception as e:
        logger.error(f"[BUFFER ERRO] Falha ao recuperar/limpar buffer atomicamente no Redis: {e}")
        try:
            chave_buffer = f"buffer:{telefone}"
            chave_tempo = f"last_msg_time:{telefone}"
            msgs = await redis_client.lrange(chave_buffer, 0, -1)
            await redis_client.delete(chave_buffer, chave_tempo)
            return msgs or []
        except Exception as inner_e:
            logger.error(f"[BUFFER ERRO CRÍTICO] Fallback no Redis falhou: {inner_e}")
            raise BufferOperationError(f"Falha irrecuperável no buffer Redis para {telefone}: {inner_e}") from inner_e
