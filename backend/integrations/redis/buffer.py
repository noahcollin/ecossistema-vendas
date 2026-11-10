import time
import uuid
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

# Script Lua atômico para liberação segura de lock distribuído (só remove se o token coincidir)
LUA_LIBERAR_LOCK = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
else
    return 0
end
"""

_VOLATILE_PATTERNS = (
    "buffer:*",
    "last_msg_time:*",
    "pacing:*",
    "lock:inbound:*",
)


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
            # Para inteiros como nanossegundos (time_ns), igualdade estrita de strings já define se é a última
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


async def listar_telefones_com_buffer() -> list[str]:
    """
    Lista de forma não-bloqueante (via SCAN) todos os telefones que possuem buffer pendente.
    Substitui o comando bloqueante KEYS 'buffer:*' em inicializações e healthchecks.
    """
    telefones: list[str] = []
    try:
        async for chave in redis_client.scan_iter(match="buffer:*", count=100):
            chave_str = chave.decode("utf-8") if isinstance(chave, bytes) else str(chave)
            telefone = chave_str.replace("buffer:", "", 1).strip()
            if telefone:
                telefones.append(telefone)
    except Exception as e:
        logger.warning(f"[BUFFER SCAN] ⚠️ Não foi possível varrer buffers pendentes no Redis: {e}")
    return telefones


async def contar_buffers_pendentes() -> int:
    """Retorna a contagem de buffers ativos sem bloquear a thread principal do Redis."""
    return len(await listar_telefones_com_buffer())


async def registrar_marcador_bot(msg_id: str, ttl_segundos: int = 120) -> None:
    """Marca um ID de mensagem outbound como disparada pelo sistema para evitar falso Zero-Click Takeover."""
    if not msg_id:
        return
    try:
        await redis_client.setex(f"bot_outbound:{msg_id}", ttl_segundos, "1")
    except Exception as e:
        logger.debug(f"[BUFFER BOT MARKER] Falha não-crítica ao gravar marcador {msg_id}: {e}")


async def verificar_marcador_bot(msg_id: str) -> bool:
    """Verifica se uma mensagem fromMe=True foi enviada pelo próprio ecossistema (API/Painel)."""
    if not msg_id:
        return False
    try:
        if await redis_client.get(f"bot_outbound:{msg_id}"):
            return True
        if ":" in str(msg_id):
            sufixo = str(msg_id).split(":")[-1]
            return bool(await redis_client.get(f"bot_outbound:{sufixo}"))
    except Exception:
        return False
    return False


async def adquirir_lock(chave: str, ttl_segundos: int = 45) -> str | None:
    """
    Adquire lock distribuído exclusivo (SET NX EX) para serializar processamento por telefone/lead.
    Retorna o token proprietário em caso de sucesso ou None se o lock já estiver ocupado.
    Em caso de indisponibilidade transitória do Redis, opera em modo fail-open com token local.
    """
    token = uuid.uuid4().hex
    try:
        adquirido = await redis_client.set(chave, token, nx=True, ex=ttl_segundos)
        return token if adquirido else None
    except Exception as e:
        logger.warning(f"[REDIS LOCK] ⚠️ Falha ao adquirir lock '{chave}' (fail-open ativado): {e}")
        return f"failopen:{token}"


async def liberar_lock(chave: str, token: str) -> bool:
    """Libera atomicamente um lock distribuído somente se o token pertencer ao chamador."""
    if not token or token.startswith("failopen:"):
        return True
    try:
        removido = await redis_client.eval(LUA_LIBERAR_LOCK, 1, chave, token)
        return bool(removido)
    except Exception as e:
        logger.debug(f"[REDIS LOCK] Falha ao liberar lock '{chave}': {e}")
        return False


async def expurgar_filas_volateis() -> int:
    """
    Expurga de forma não-bloqueante (SCAN + UNLINK/DEL em lotes) todas as chaves voláteis
    de debounce, carimbos de tempo e locks de processamento sem afetar o PostgreSQL.
    """
    chaves_para_remover: list[str] = []
    for padrao in _VOLATILE_PATTERNS:
        async for chave in redis_client.scan_iter(match=padrao, count=200):
            chave_str = chave.decode("utf-8") if isinstance(chave, bytes) else str(chave)
            chaves_para_remover.append(chave_str)

    if not chaves_para_remover:
        return 0

    removidas = 0
    tamanho_lote = 200
    for idx in range(0, len(chaves_para_remover), tamanho_lote):
        lote = chaves_para_remover[idx : idx + tamanho_lote]
        removidas += int(await redis_client.delete(*lote))

    logger.warning(f"[REDIS PURGE] 🧹 {removidas} chave(s) voláteis expurgadas manualmente.")
    return removidas
