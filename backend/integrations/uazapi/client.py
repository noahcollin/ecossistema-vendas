import asyncio
import httpx
from core.logger import logger
from core.config import settings
from core.utils import dividir_mensagens_whatsapp
from integrations.redis.buffer import redis_client

_shared_client: httpx.AsyncClient | None = None

def get_uazapi_client() -> httpx.AsyncClient:
    """
    Retorna o cliente HTTP compartilhado com pool de conexões (Keep-Alive).
    Elimina o anti-pattern de socket churn e reduz latência de TLS.
    """
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.UAZAPI_TIMEOUT_SECONDS, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=50, max_connections=100)
        )
    return _shared_client

async def close_uazapi_client():
    """Encerra o cliente HTTP compartilhado de forma graciosa."""
    global _shared_client
    if _shared_client and not _shared_client.is_closed:
        await _shared_client.aclose()
        _shared_client = None

async def enviar_presenca(telefone: str, presenca: str = "composing", delay_ms: int = 15000) -> dict:
    """
    Atualiza o status de presença da conversa no WhatsApp (ex: 'composing' para 'digitando...'
    ou 'recording' para 'gravando áudio...').
    """
    if not settings.UAZAPI_TOKEN:
        logger.warning("[UAZAPI PRESENÇA] UAZAPI_TOKEN não está configurado.")
        return {"status": "erro", "detalhe": "Token não configurado"}

    url = f"{settings.UAZAPI_URL}/message/presence"
    headers = {
        "Content-Type": "application/json",
        "token": settings.UAZAPI_TOKEN
    }
    body = {
        "number": telefone,
        "presence": presenca,
        "delay": delay_ms
    }

    try:
        client = get_uazapi_client()
        resposta = await client.post(url, headers=headers, json=body)
        resposta.raise_for_status()
        logger.info(f"[UAZAPI PRESENÇA] Status '{presenca}' enviado para {telefone}")
        return {"status": "sucesso"}
    except Exception as e:
        logger.warning(f"[UAZAPI PRESENÇA] Falha ao enviar presença '{presenca}': {e}")
        return {"status": "erro", "detalhe": str(e)}

async def enviar_mensagem(telefone: str, texto: str, delay_ms: int = 2000, max_retries: int = 2) -> dict:
    """
    Envia uma mensagem de texto para o número fornecido via Uazapi.
    Ativa automaticamente readchat=True para marcar a mensagem do lead como lida.
    Possui política de retries automáticos com backoff para resiliência de rede.
    """
    if not settings.UAZAPI_TOKEN:
        logger.error("[UAZAPI SEND] UAZAPI_TOKEN não está configurado no arquivo .env!")
        return {"status": "erro", "detalhe": "Token não configurado"}
        
    url = f"{settings.UAZAPI_URL}/send/text"
    headers = {
        "Content-Type": "application/json",
        "token": settings.UAZAPI_TOKEN
    }
    
    body = {
        "number": telefone,
        "text": texto,
        "delay": str(delay_ms),
        "readchat": True,
        "readmessages": True
    }
    
    tentativa = 0
    client = get_uazapi_client()
    
    while tentativa <= max_retries:
        try:
            resposta = await client.post(url, headers=headers, json=body)
            resposta.raise_for_status()
            
            dados = resposta.json()
            itens = [dados] if isinstance(dados, dict) else (dados if isinstance(dados, list) else [])
            for item in itens:
                if isinstance(item, dict):
                    msg_id = item.get("id") or item.get("messageid") or item.get("messageId")
                    if not msg_id and isinstance(item.get("key"), dict):
                        msg_id = item["key"].get("id")
                    if msg_id:
                        try:
                            await redis_client.setex(f"bot_outbound:{msg_id}", 300, "1")
                            if ":" in str(msg_id):
                                await redis_client.setex(f"bot_outbound:{str(msg_id).split(':')[-1]}", 300, "1")
                        except Exception:
                            pass

            logger.info(f"[UAZAPI SEND] 🚀 Mensagem enviada para {telefone} com sucesso!")
            return {"status": "sucesso", "dados": dados}
            
        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as e:
            tentativa += 1
            if tentativa <= max_retries:
                espera = tentativa * 1.5
                logger.warning(f"[UAZAPI SEND RETRY] ⚠️ Falha transitória ({e}). Tentativa {tentativa}/{max_retries} em {espera}s...")
                await asyncio.sleep(espera)
            else:
                logger.error(f"[UAZAPI SEND] ❌ Falha definitiva após {max_retries} tentativas: {e}")
                return {"status": "erro", "detalhe": str(e)}
        except httpx.HTTPStatusError as e:
            erro = e.response.text
            logger.error(f"[UAZAPI SEND] ❌ Erro da API Uazapi ({e.response.status_code}): {erro}")
            return {"status": "erro", "detalhe": erro}
        except Exception as e:
            logger.error(f"[UAZAPI SEND] ❌ Falha na comunicação: {str(e)}")
            return {"status": "erro", "detalhe": str(e)}
            
    return {"status": "erro", "detalhe": "Max retries excedido"}


async def enviar_mensagem_humanizada(
    telefone: str,
    texto_bruto: str,
    delay_base_ms: int = 1500,
    simular_digitacao: bool = True,
    intervalo_entre_baloes: float = 1.8
) -> tuple[list[str], bool]:
    """
    Orquestra o envio de uma mensagem comercial dividida em balões humanizados.
    Garante que qualquer mensagem da IA (Inbound, Follow-up, Reativação):
    1. Passe pela fragmentação inteligente (dividir_mensagens_whatsapp).
    2. Seja enviada sequencialmente simulando presença de digitação ('composing') no WhatsApp.
    3. Mantenha espaçamento temporal natural entre cada balão (~1.8s) para nunca inundar o cliente.

    Retorna:
        tuple[list[str], bool]: (baloes_efetivamente_enviados, sucesso_geral)
    """
    if not texto_bruto or not texto_bruto.strip():
        return [], False

    baloes = dividir_mensagens_whatsapp(texto_bruto)
    if not baloes:
        baloes = [texto_bruto.strip()]

    baloes_enviados: list[str] = []
    todos_enviados_com_sucesso = True

    for idx, parte in enumerate(baloes):
        if not parte.strip():
            continue

        # Para balões subsequentes, simula digitação e pausa orgânica antes do disparo
        if idx > 0 and simular_digitacao:
            await enviar_presenca(telefone, presenca="composing", delay_ms=3000)
            tempo_pausa = min(max(len(parte) * 0.015, intervalo_entre_baloes), intervalo_entre_baloes + 1.0)
            await asyncio.sleep(tempo_pausa)
        elif idx == 0 and simular_digitacao:
            # Digitação inicial breve para o primeiro balão
            await enviar_presenca(telefone, presenca="composing", delay_ms=2500)
            await asyncio.sleep(1.2)

        res = await enviar_mensagem(telefone, parte, delay_ms=delay_base_ms)
        if isinstance(res, dict) and res.get("status") == "erro":
            logger.error(
                f"[UAZAPI HUMANIZADO] ❌ Falha no disparo do balão {idx + 1}/{len(baloes)} para {telefone}: {res}"
            )
            todos_enviados_com_sucesso = False
            break

        baloes_enviados.append(parte)

    return baloes_enviados, todos_enviados_com_sucesso


async def baixar_arquivo(message_id: str, generate_mp3: bool = False) -> dict:
    """
    Solicita o download do arquivo de uma mensagem diretamente via API da Uazapi.
    Retorna dicionário com base64Data, fileURL, mimetype, etc.
    """
    if not settings.UAZAPI_TOKEN:
        logger.warning("[UAZAPI DOWNLOAD] UAZAPI_TOKEN não configurado para download de mídia.")
        return {}
        
    url = f"{settings.UAZAPI_URL}/message/download"
    headers = {
        "Content-Type": "application/json",
        "token": settings.UAZAPI_TOKEN
    }
    
    id_limpo = message_id.split(":")[-1] if ":" in message_id else message_id
    
    body = {
        "id": id_limpo,
        "return_base64": True,
        "return_link": True
    }
    
    if generate_mp3:
        body["generate_mp3"] = True
    
    try:
        client = get_uazapi_client()
        resposta = await client.post(url, headers=headers, json=body)
        if resposta.status_code == 200:
            dados = resposta.json()
            logger.info(f"[UAZAPI DOWNLOAD] 📥 Arquivo da mensagem {id_limpo} baixado com sucesso")
            return dados
        else:
            logger.warning(f"[UAZAPI DOWNLOAD] Falha ao baixar arquivo ({resposta.status_code}): {resposta.text}")
            return {}
    except Exception as e:
        logger.error(f"[UAZAPI DOWNLOAD ERRO] Falha ao contatar /message/download: {e}")
        return {}
