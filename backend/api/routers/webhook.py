"""
Controlador HTTP de Entrada do Webhook WhatsApp (Uazapi).
Camada estritamente de transporte/segurança: autentica o segredo via HMAC timing-safe
e delega 100% das regras de negócio ao WebhookApplicationService (Clean Architecture).
"""

import hmac
import json
from typing import Any
from fastapi import APIRouter, Header, Query, HTTPException, Request, status, Depends

from core.config import settings
from core.logger import logger
from services.inbound import WebhookApplicationService, SendEventService
import schemas

router = APIRouter(prefix="/webhook", tags=["Webhook (WhatsApp / Send Inteligentte)"])


async def validar_webhook_secret(
    x_webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
    secret: str | None = Query(None)
) -> None:
    """
    Valida a autenticidade da requisição do webhook via segredo configurado no .env.
    Utiliza hmac.compare_digest para imunidade contra ataques de temporização (timing attacks).
    """
    token_esperado = (settings.WEBHOOK_SECRET_TOKEN or "").strip()
    if token_esperado:
        token_fornecido = (x_webhook_secret or secret or "").strip()
        if not token_fornecido or not hmac.compare_digest(token_fornecido, token_esperado):
            logger.warning("[SEGURANÇA WEBHOOK] 🛑 Acesso não autorizado ao webhook: token inválido ou ausente.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Acesso não autorizado: Token secreto do webhook inválido ou ausente."
            )


@router.post("", dependencies=[Depends(validar_webhook_secret)])
@router.post("/", dependencies=[Depends(validar_webhook_secret)])
@router.post("/uazapi", dependencies=[Depends(validar_webhook_secret)])
@router.post("/whatsapp", dependencies=[Depends(validar_webhook_secret)])
async def webhook_uazapi(payload: schemas.UazapiPayload) -> dict[str, Any]:
    """Recebe eventos da Uazapi em < 5ms e delega a triagem ao Application Service."""
    try:
        # Quando SEND_API_KEY está ativa, a Uazapi opera apenas como notificador de saída para o Eduardo.
        # Ignora webhooks de conversas recebidas no chip da Uazapi para que a IA nunca responda contatos daquele chip.
        if settings.SEND_API_KEY and payload.instanceName != "send_inteligentte":
            logger.info("[WEBHOOK UAZAPI] 🛡️ Evento recebido na Uazapi ignorado (operação ativa no Send Inteligentte; Uazapi dedicada a alertas do Supervisor).")
            return {"status": "ignorado", "motivo": "uazapi_dedicada_apenas_notificacao_supervisor"}
        return await WebhookApplicationService.processar_evento_uazapi(payload)
    except Exception as e:
        logger.error(f"[WEBHOOK ERRO] ❌ Falha crítica ao processar requisição: {e}", exc_info=True)
        return {"status": "erro", "detalhe": str(e)}


@router.post("/send")
async def webhook_send_inteligentte(
    request: Request,
    x_send_timestamp: str | None = Header(None, alias="X-Send-Timestamp"),
    x_send_signature: str | None = Header(None, alias="X-Send-Signature"),
) -> dict[str, Any]:
    """
    Recebe eventos em tempo real do Send Inteligentte (API Oficial Meta).
    Valida assinatura HMAC-SHA256 quando SEND_WEBHOOK_SECRET estiver configurado.
    """
    raw_body = await request.body()
    if not SendEventService.verificar_assinatura_webhook(
        raw_body=raw_body,
        timestamp=x_send_timestamp,
        signature=x_send_signature,
    ):
        logger.warning("[SEND WEBHOOK] 🛑 Assinatura HMAC-SHA256 inválida ou expirada.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Assinatura X-Send-Signature inválida ou expirada.",
        )

    try:
        evento = json.loads(raw_body.decode("utf-8"))
        return await SendEventService.processar_evento_send(evento)
    except Exception as e:
        logger.error(f"[SEND WEBHOOK ERRO] ❌ Falha ao processar evento do Send: {e}", exc_info=True)
        return {"status": "erro", "detalhe": str(e)}
