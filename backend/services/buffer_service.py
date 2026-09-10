import os
import time
from redis import asyncio as aioredis
from core.logger import logger

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Pool de conexão assíncrona global para o Redis
redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)

async def adicionar_mensagem(telefone: str, texto: str) -> float:
    """
    Enfileira o fragmento de mensagem no buffer do lead no Redis
    e atualiza o carimbo de data/hora (timestamp) da última mensagem.
    Retorna o timestamp gerado.
    """
    try:
        agora = time.time()
        chave_buffer = f"buffer:{telefone}"
        chave_tempo = f"last_msg_time:{telefone}"
        
        # Operação assíncrona atômica no Redis
        async with redis_client.pipeline(transaction=True) as pipe:
            pipe.rpush(chave_buffer, texto)
            pipe.set(chave_tempo, str(agora))
            # Define expiração de 10 minutos para evitar sujeira se o sistema reiniciar
            pipe.expire(chave_buffer, 600)
            pipe.expire(chave_tempo, 600)
            await pipe.execute()
            
        logger.info(f"[BUFFER] 📥 Mensagem de {telefone} enfileirada no Redis. Carimbo: {agora:.3f}")
        return agora
    except Exception as e:
        logger.error(f"[BUFFER ERRO] Falha ao adicionar mensagem no Redis: {e}")
        return time.time()

async def verificar_se_e_ultima(telefone: str, timestamp_disparado: float) -> bool:
    """
    Verifica se o timestamp gravado no Redis ainda coincide com o timestamp
    desta tarefa. Se outra mensagem tiver chegado no intervalo, retorna False.
    """
    try:
        chave_tempo = f"last_msg_time:{telefone}"
        ultimo_tempo = await redis_client.get(chave_tempo)
        
        if not ultimo_tempo:
            return False
            
        # Converte para float e compara
        delta = abs(float(ultimo_tempo) - timestamp_disparado)
        # Se a diferença for minúscula (< 0.0001s), é a mesma execução
        return delta < 0.0001
    except Exception as e:
        logger.error(f"[BUFFER ERRO] Falha ao verificar timestamp no Redis: {e}")
        return False

async def obter_e_limpar_buffer(telefone: str) -> list[str]:
    """
    Recupera todas as mensagens acumuladas no buffer do lead e limpa as chaves.
    """
    try:
        chave_buffer = f"buffer:{telefone}"
        chave_tempo = f"last_msg_time:{telefone}"
        
        mensagens = await redis_client.lrange(chave_buffer, 0, -1)
        
        # Limpa o buffer e o carimbo
        await redis_client.delete(chave_buffer)
        await redis_client.delete(chave_tempo)
        
        logger.info(f"[BUFFER] 📦 {len(mensagens)} mensagens consolidadas e retiradas do buffer de {telefone}")
        return mensagens or []
    except Exception as e:
        logger.error(f"[BUFFER ERRO] Falha ao recuperar/limpar buffer no Redis: {e}")
        return []
