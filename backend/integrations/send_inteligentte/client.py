"""
Cliente HTTP Assíncrono para a API de Agentes do Send Inteligentte (Meta Cloud API).
Implementa exatamente o contrato oficial:
- GET  /api/v1/events?after={seq}&limit={limit}
- POST /api/v1/messages/text
- POST /api/v1/conversations/{phone}/handover
- GET  /api/v1/media/{mediaId}

Respeita estritamente as regras de erro e retentativa (Seção 10 da especificação):
- NUNCA retenta 409 HUMAN_HANDOVER, 422 OPT_OUT, 422 BLACKLISTED, 422 OUTSIDE_WINDOW.
- Retenta com backoff exponencial em 429 RATE_LIMITED, 500, 502 META_ERROR e timeouts de rede.
"""

import asyncio
import base64
from typing import Any, Optional
import httpx

from core.config import settings
from core.logger import logger
from integrations.redis.buffer import redis_client

_send_client: httpx.AsyncClient | None = None

CODIGOS_NAO_RETENTAR = {
    "HUMAN_HANDOVER",
    "OPT_OUT",
    "BLACKLISTED",
    "OUTSIDE_WINDOW",
}


def limpar_telefone_send(telefone: str) -> str:
    """
    Normaliza o telefone para o formato esperado pelo Send Inteligentte:
    apenas dígitos com DDI, sem '+' (ex: '5583999990001').
    """
    digitos = "".join(filter(str.isdigit, str(telefone or "")))
    if digitos and len(digitos) in (10, 11) and not digitos.startswith("55"):
        digitos = f"55{digitos}"
    return digitos


def _obter_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.SEND_API_KEY}",
        "Content-Type": "application/json",
    }


def get_send_client() -> httpx.AsyncClient:
    """Retorna cliente HTTP com Keep-Alive compartilhado para o Send Inteligentte."""
    global _send_client
    if _send_client is None or _send_client.is_closed:
        _send_client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.UAZAPI_TIMEOUT_SECONDS, connect=5.0),
            limits=httpx.Limits(max_keepalive_connections=50, max_connections=100),
        )
    return _send_client


async def close_send_client() -> None:
    """Encerra o cliente HTTP compartilhado do Send Inteligentte."""
    global _send_client
    if _send_client and not _send_client.is_closed:
        await _send_client.aclose()
        _send_client = None


async def buscar_eventos_send(after: int = 0, limit: int = 50) -> dict[str, Any]:
    """
    Consome a fila de eventos do Send Inteligentte via cursor incremental:
    GET /api/v1/events?after={after}&limit={limit}
    """
    if not settings.SEND_API_KEY:
        return {"events": [], "nextAfter": after, "hasMore": False}

    base_url = settings.SEND_API_URL.rstrip("/")
    url = f"{base_url}/events"
    params = {"after": max(0, int(after)), "limit": min(max(1, int(limit)), 200)}

    try:
        client = get_send_client()
        resp = await client.get(url, headers=_obter_headers(), params=params)
        if resp.status_code == 200:
            dados = resp.json()
            return {
                "events": dados.get("events", []),
                "nextAfter": dados.get("nextAfter", after),
                "hasMore": bool(dados.get("hasMore", False)),
            }
        logger.warning(f"[SEND EVENTS] ⚠️ Status inesperado {resp.status_code} ao buscar eventos: {resp.text}")
        return {"events": [], "nextAfter": after, "hasMore": False}
    except Exception as exc:
        logger.warning(f"[SEND EVENTS] ⚠️ Falha de rede ao consultar /events: {exc}")
        return {"events": [], "nextAfter": after, "hasMore": False}


async def enviar_mensagem_send(
    telefone: str,
    texto: str,
    reply_to_wamid: Optional[str] = None,
    max_retries: int = 2,
) -> dict[str, Any]:
    """
    Envia uma mensagem de texto livre dentro da janela de 24h da Meta via Send Inteligentte:
    POST /api/v1/messages/text
    """
    if not settings.SEND_API_KEY:
        logger.error("[SEND INTELIGENTTE] SEND_API_KEY não configurada!")
        return {"status": "erro", "detalhe": "SEND_API_KEY não configurada"}

    telefone_limpo = limpar_telefone_send(telefone)
    base_url = settings.SEND_API_URL.rstrip("/")
    url = f"{base_url}/messages/text"

    body: dict[str, Any] = {
        "to": telefone_limpo,
        "text": (texto or "")[:4096],
    }
    if reply_to_wamid:
        body["replyToWamid"] = reply_to_wamid

    tentativa = 0
    client = get_send_client()

    while tentativa <= max_retries:
        try:
            resp = await client.post(url, headers=_obter_headers(), json=body)

            if resp.status_code in (200, 201):
                dados = resp.json()
                msg_id = dados.get("id")
                wamid = dados.get("wamid")
                for identificador in (msg_id, wamid):
                    if identificador:
                        try:
                            await redis_client.setex(f"bot_outbound:{identificador}", 300, "1")
                        except Exception:
                            pass

                logger.info(f"[SEND INTELIGENTTE] 🚀 Mensagem enviada para {telefone_limpo} (wamid: {wamid})!")
                return {"status": "sucesso", "dados": dados}

            # Erros de regra de negócio (409 / 422 / 400 / 401 / 403): NUNCA retentar
            if resp.status_code in (400, 401, 403, 404, 409, 422):
                codigo_erro = "UNKNOWN"
                try:
                    err_json = resp.json()
                    codigo_erro = err_json.get("code") or err_json.get("error") or "UNKNOWN"
                except Exception:
                    pass

                logger.warning(
                    f"[SEND INTELIGENTTE] 🛑 Envio recusado sem retry para {telefone_limpo} "
                    f"(HTTP {resp.status_code} | code={codigo_erro}): {resp.text}"
                )
                return {
                    "status": "erro",
                    "code": codigo_erro,
                    "status_code": resp.status_code,
                    "nao_retentar": True,
                    "detalhe": resp.text,
                }

            # Erros transitórios (429 RATE_LIMITED, 500, 502 META_ERROR, 503, 504): Retentar com backoff
            tentativa += 1
            if tentativa <= max_retries:
                espera = tentativa * 2.0 if resp.status_code == 429 else tentativa * 1.5
                logger.warning(
                    f"[SEND RETRY] ⚠️ HTTP {resp.status_code} ao enviar para {telefone_limpo}. "
                    f"Tentativa {tentativa}/{max_retries} em {espera}s..."
                )
                await asyncio.sleep(espera)
            else:
                logger.error(
                    f"[SEND INTELIGENTTE] ❌ Falha definitiva após {max_retries} tentativas "
                    f"(HTTP {resp.status_code}): {resp.text}"
                )
                return {"status": "erro", "status_code": resp.status_code, "detalhe": resp.text}

        except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError) as exc:
            tentativa += 1
            if tentativa <= max_retries:
                espera = tentativa * 1.5
                logger.warning(
                    f"[SEND RETRY] ⚠️ Falha transitória de rede ({exc}). "
                    f"Tentativa {tentativa}/{max_retries} em {espera}s..."
                )
                await asyncio.sleep(espera)
            else:
                logger.error(f"[SEND INTELIGENTTE] ❌ Falha definitiva de rede após {max_retries} tentativas: {exc}")
                return {"status": "erro", "detalhe": str(exc)}
        except Exception as exc:
            logger.error(f"[SEND INTELIGENTTE] ❌ Erro inesperado ao enviar mensagem: {exc}")
            return {"status": "erro", "detalhe": str(exc)}

    return {"status": "erro", "detalhe": "Max retries excedido"}


async def solicitar_handover_send(telefone: str, reason: str) -> dict[str, Any]:
    """
    Transfere a conversa para atendimento humano no Live Chat do Send Inteligentte:
    POST /api/v1/conversations/{phone}/handover
    Pausa o agente por 24h no Send e coloca o lead na fila 'Aguardando resposta'.
    """
    if not settings.SEND_API_KEY:
        return {"status": "ignorado", "detalhe": "SEND_API_KEY não configurada"}

    telefone_limpo = limpar_telefone_send(telefone)
    base_url = settings.SEND_API_URL.rstrip("/")
    url = f"{base_url}/conversations/{telefone_limpo}/handover"
    body = {"reason": (reason or "Reunião de Diagnóstico Aprovada com o Eduardo")[:500]}

    try:
        client = get_send_client()
        resp = await client.post(url, headers=_obter_headers(), json=body)
        if resp.status_code in (200, 201):
            dados = resp.json()
            logger.info(
                f"[SEND HANDOVER] 🤝 Handover registrado no Send Inteligentte para {telefone_limpo} "
                f"(resumesAt: {dados.get('resumesAt')})."
            )
            return {"status": "sucesso", "dados": dados}

        logger.warning(
            f"[SEND HANDOVER] ⚠️ Não foi possível registrar handover no Send para {telefone_limpo} "
            f"(HTTP {resp.status_code}): {resp.text}"
        )
        return {"status": "erro", "status_code": resp.status_code, "detalhe": resp.text}
    except Exception as exc:
        logger.warning(f"[SEND HANDOVER] ⚠️ Falha ao chamar /handover no Send para {telefone_limpo}: {exc}")
        return {"status": "erro", "detalhe": str(exc)}


async def baixar_midia_send(media_id: str) -> dict[str, Any]:
    """
    Faz download de mídia (áudio, imagem, documento, vídeo) via proxy autenticado do Send:
    GET /api/v1/media/{mediaId}
    Retorna dicionário compatível com o MediaPipeline (`base64Data` e `mimetype`).
    """
    if not settings.SEND_API_KEY or not media_id:
        return {}

    id_limpo = media_id.split(":")[-1] if ":" in media_id else media_id
    base_url = settings.SEND_API_URL.rstrip("/")
    url = f"{base_url}/media/{id_limpo}"

    try:
        client = get_send_client()
        headers = {"Authorization": f"Bearer {settings.SEND_API_KEY}"}
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200 and resp.content:
            content_type = resp.headers.get("content-type", "application/octet-stream")
            mimetype = content_type.split(";")[0].strip()
            b64_data = base64.b64encode(resp.content).decode("utf-8")
            logger.info(
                f"[SEND MEDIA] 📥 Mídia {id_limpo} baixada do Send Inteligentte "
                f"({len(resp.content)} bytes | {mimetype})"
            )
            return {
                "base64Data": b64_data,
                "mimetype": mimetype,
            }

        logger.warning(f"[SEND MEDIA] ⚠️ Falha ao baixar mídia {id_limpo} no Send (HTTP {resp.status_code})")
        return {}
    except Exception as exc:
        logger.error(f"[SEND MEDIA ERRO] ❌ Erro ao baixar mídia {id_limpo} do Send: {exc}")
        return {}

