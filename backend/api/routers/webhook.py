import asyncio
import json
import hmac
from typing import Any
from fastapi import APIRouter, Header, Query, HTTPException, status, Depends

from core.logger import logger
from core.config import settings
from core.database import AsyncSessionLocal
from core.utils import normalizar_telefone
from repositories.lead_repository import LeadRepository
from services.transbordo_service import TransbordoService
from services.inbound_service import InboundService
from integrations.redis import buffer as buffer_service
import schemas

router = APIRouter(prefix="/webhook", tags=["Webhook (Uazapi)"])


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
    """
    Webhook Receptivo: Enfileira mensagens recebidas no buffer Redis em < 5ms
    e delega o pipeline conversacional para o InboundService em segundo plano.
    Aplica guardas contra loops infinitos (fromMe), grupos (@g.us) e ACKs fantasmas.
    """
    try:
        if not payload.chat or not payload.chat.phone:
            return {"status": "ignorado", "motivo": "sem_telefone"}

        telefone_raw = payload.chat.phone

        # 🛑 1. GUARDA ANTI-GRUPO E ANTI-CANAIS: Ignora grupos, canais e newsletters do WhatsApp
        if (
            "@g.us" in telefone_raw
            or "@newsletter" in telefone_raw
            or "@broadcast" in telefone_raw
            or getattr(payload.chat, "isGroup", False)
            or getattr(payload.chat, "isNewsletter", False)
            or (payload.message and (getattr(payload.message, "isGroup", False) or getattr(payload.message, "isNewsletter", False)))
        ):
            logger.info(f"[WEBHOOK] 🛑 Mensagem de grupo/canal ignorada ({telefone_raw}).")
            return {"status": "ignorado", "motivo": "mensagem_de_grupo_ou_canal"}

        # 🛑 2. TRATAMENTO DE MENSAGENS ENVIADAS (fromMe=True)
        if payload.message and getattr(payload.message, "fromMe", False):
            msg_id = payload.message.id or payload.message.messageid
            foi_bot = False
            if msg_id:
                try:
                    foi_bot = bool(await buffer_service.redis_client.get(f"bot_outbound:{msg_id}"))
                    if not foi_bot and ":" in str(msg_id):
                        foi_bot = bool(await buffer_service.redis_client.get(f"bot_outbound:{str(msg_id).split(':')[-1]}"))
                except Exception:
                    pass

            sender_name = (
                payload.message.senderName
                or (payload.chat.name if payload.chat and payload.chat.name != "Bot" else None)
                or "Atendente Humano"
            )
            is_bot_chat = bool(payload.chat and payload.chat.name == "Bot")

            if (
                getattr(payload.message, "wasSentByApi", False)
                or foi_bot
                or is_bot_chat
            ):
                logger.debug("[WEBHOOK] 🔄 Mensagem própria do bot ignorada (fromMe=True).")
                return {"status": "ignorado", "motivo": "mensagem_do_proprio_bot"}

            # 👤 ZERO-CLICK TAKEOVER / OUTBOUND HUMANO: Atendente humano digitando no WhatsApp
            texto_humano = payload.message.text or ""
            if texto_humano.strip():
                telefone_norm = normalizar_telefone(telefone_raw)
                async with AsyncSessionLocal() as db_human:
                    lead_human = await LeadRepository.get_by_phone(db_human, telefone_norm)
                    if lead_human:
                        await TransbordoService.capturar_mensagem_humana_whatsapp(
                            db=db_human,
                            lead=lead_human,
                            texto=texto_humano.strip(),
                            sender_name=sender_name
                        )
                        logger.info(f"[ZERO-CLICK TAKEOVER] 👤 Intervenção humana capturada para {telefone_norm}.")
                        return {"status": "capturada_intervencao_humana", "telefone": telefone_norm}
                    else:
                        nome_lead = payload.chat.name or sender_name
                        await TransbordoService.iniciar_atendimento_humano_outbound(
                            db=db_human,
                            telefone=telefone_norm,
                            nome_contato=nome_lead,
                            texto=texto_humano.strip(),
                            sender_name=sender_name
                        )
                        logger.info(f"[OUTBOUND HUMANO] 👤 Novo lead criado por humano para {telefone_norm}.")
                        return {"status": "iniciado_outbound_humano", "telefone": telefone_norm}

            return {"status": "ignorado", "motivo": "mensagem_do_proprio_bot"}

        # 🛑 3. GUARDA DE EVENTOS FANTASMAS / ACKs VAZIOS
        if not payload.message:
            return {"status": "ignorado", "motivo": "evento_sem_mensagem"}

        tem_texto = bool(payload.message.text and payload.message.text.strip())
        tem_midia = bool(payload.message.fileURL or payload.message.messageType or payload.message.content)
        if not tem_texto and not tem_midia:
            return {"status": "ignorado", "motivo": "conteudo_vazio"}

        # Normaliza o telefone para formato canônico (+55...)
        telefone = normalizar_telefone(telefone_raw)
        if not telefone or len("".join(filter(str.isdigit, telefone))) < 8:
            return {"status": "ignorado", "motivo": "telefone_invalido"}

        nome_contato = payload.chat.name or (payload.message.senderName if payload.message else "Desconhecido")

        # 🛡️ TRAVA DE SEGURANÇA: Sandbox de testes
        if settings.SANDBOX_MODE:
            apenas_digitos = "".join(filter(str.isdigit, telefone))
            if not apenas_digitos.endswith(settings.WHITELIST_PHONE_SUFFIX):
                logger.info(f"[SEGURANÇA] 🛑 Mensagem de {telefone} ignorada (fora da whitelist de teste).")
                return {"status": "ignorado", "motivo": "numero_fora_da_whitelist_de_teste"}

        # Enfileira os dados da mensagem imediatamente no Redis (mode="json" e default=str para tipos complexos)
        dados_msg = payload.message.model_dump(mode="json")
        timestamp_disparo = await buffer_service.adicionar_mensagem(
            telefone, json.dumps(dados_msg, default=str)
        )

        # Dispara background task para aguardar a janela de debounce no InboundService
        asyncio.create_task(InboundService.processar_debounce(telefone, nome_contato, timestamp_disparo))

        # Responde à Uazapi em milissegundos
        return {"status": "enfileirado_com_debounce", "telefone": telefone}

    except Exception as e:
        logger.error(f"[WEBHOOK ERRO] ❌ Falha crítica ao processar requisição: {e}", exc_info=True)
        return {"status": "erro", "detalhe": str(e)}
