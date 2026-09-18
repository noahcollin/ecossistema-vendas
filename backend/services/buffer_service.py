import time
from redis import asyncio as aioredis
from core.logger import logger
from core.config import settings

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
        
        # Operação assíncrona atômica no Redis
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.rpush(chave_buffer, texto)
            pipe.set(chave_tempo, token_tempo)
            # Define expiração de 10 minutos para evitar sujeira se o sistema reiniciar
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
            
        token_str = str(token_disparado)
        if ultimo_tempo == token_str:
            return True
            
        # Fallback de compatibilidade para floats legados
        try:
            return abs(float(ultimo_tempo) - float(token_disparado)) < 0.0001
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
        
        # Execução atômica no Redis (sem risco de perda de mensagens entre leitura e exclusão)
        mensagens = await redis_client.eval(LUA_OBTER_E_LIMPAR, 2, chave_buffer, chave_tempo)
        
        logger.info(f"[BUFFER] 📦 {len(mensagens or [])} mensagens consolidadas e retiradas atomicamente de {telefone}")
        return mensagens or []
    except Exception as e:
        logger.error(f"[BUFFER ERRO] Falha ao recuperar/limpar buffer atomicamente no Redis: {e}")
        # Fallback defensivo não atômico se eval falhar
        try:
            chave_buffer = f"buffer:{telefone}"
            chave_tempo = f"last_msg_time:{telefone}"
            msgs = await redis_client.lrange(chave_buffer, 0, -1)
            await redis_client.delete(chave_buffer, chave_tempo)
            return msgs or []
        except Exception as inner_e:
            logger.error(f"[BUFFER ERRO CRÍTICO] Fallback no Redis falhou: {inner_e}")
            return []
