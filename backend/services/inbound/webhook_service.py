"""
Application Service para Triagem e Recepção de Eventos do Webhook WhatsApp (Uazapi).
Isola regras de negócio (filtro anti-grupo, anti-loop fromMe, Zero-Click Takeover,
Outbound Humano, trava Sandbox e enfileiramento no buffer de debounce) da camada HTTP.
"""

import json
from typing import Any, Callable
from contextlib import AbstractAsyncContextManager
from sqlalchemy.ext.asyncio import AsyncSession

from core.background import spawn_background_task
from core.config import settings
from core.database import AsyncSessionLocal
from core.logger import logger
from core.protocols import CacheBufferProtocol
from core.utils import normalizar_telefone
from integrations.redis.gateway import default_redis_buffer_gateway
from repositories.lead_repository import LeadRepository
from services.handover import TransbordoService
from services.inbound.orchestrator import InboundService
import schemas


class WebhookApplicationService:
    """
    Orquestrador de entrada do Webhook (Clean Architecture / DIP).
    Permite injeção de `buffer_gateway` e `session_factory` para testes unitários puros.
    """

    buffer_gateway: CacheBufferProtocol = default_redis_buffer_gateway
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] = AsyncSessionLocal

    @staticmethod
    def _eh_grupo_ou_canal(payload: schemas.UazapiPayload, telefone_raw: str) -> bool:
        """Identifica eventos originados em grupos (@g.us), canais (@newsletter) ou listas de transmissão."""
        return bool(
            "@g.us" in telefone_raw
            or "@newsletter" in telefone_raw
            or "@broadcast" in telefone_raw
            or getattr(payload.chat, "isGroup", False)
            or getattr(payload.chat, "isNewsletter", False)
            or (
                payload.message
                and (
                    getattr(payload.message, "isGroup", False)
                    or getattr(payload.message, "isNewsletter", False)
                )
            )
        )

    @classmethod
    async def _processar_mensagem_enviada(
        cls,
        payload: schemas.UazapiPayload,
        telefone_raw: str,
    ) -> dict[str, Any]:
        """
        Trata eventos `fromMe=True`:
        - Descarta eco das mensagens enviadas pelo próprio bot/painel (via flag da API ou marcador Redis);
        - Captura Zero-Click Takeover e Outbound Humano quando um consultor digita direto no celular/WhatsApp Web.
        """
        assert payload.message is not None
        msg_id = str(payload.message.id or payload.message.messageid or "").strip()
        foi_bot = await cls.buffer_gateway.verificar_marcador_bot(msg_id) if msg_id else False

        sender_name = (
            payload.message.senderName
            or (payload.chat.name if payload.chat and payload.chat.name != "Bot" else None)
            or "Atendente Humano"
        )
        is_bot_chat = bool(payload.chat and payload.chat.name == "Bot")

        if getattr(payload.message, "wasSentByApi", False) or foi_bot or is_bot_chat:
            logger.debug("[WEBHOOK] 🔄 Mensagem própria do bot ignorada (fromMe=True).")
            return {"status": "ignorado", "motivo": "mensagem_do_proprio_bot"}

        texto_humano = (payload.message.text or "").strip()
        if not texto_humano:
            return {"status": "ignorado", "motivo": "mensagem_do_proprio_bot"}

        telefone_norm = normalizar_telefone(telefone_raw)
        async with cls.session_factory() as db_human:
            lead_human = await LeadRepository.get_by_phone(db_human, telefone_norm)
            if lead_human:
                await TransbordoService.capturar_mensagem_humana_whatsapp(
                    db=db_human,
                    lead=lead_human,
                    texto=texto_humano,
                    sender_name=sender_name,
                )
                logger.info(f"[ZERO-CLICK TAKEOVER] 👤 Intervenção humana capturada para {telefone_norm}.")
                return {"status": "capturada_intervencao_humana", "telefone": telefone_norm}

            nome_lead = (payload.chat.name if payload.chat else None) or sender_name
            await TransbordoService.iniciar_atendimento_humano_outbound(
                db=db_human,
                telefone=telefone_norm,
                nome_contato=nome_lead,
                texto=texto_humano,
                sender_name=sender_name,
            )
            logger.info(f"[OUTBOUND HUMANO] 👤 Novo lead criado por humano para {telefone_norm}.")
            return {"status": "iniciado_outbound_humano", "telefone": telefone_norm}

    @classmethod
    async def processar_evento_uazapi(cls, payload: schemas.UazapiPayload) -> dict[str, Any]:
        """Processa um payload de evento da Uazapi em milissegundos e dispara debounce rastreado."""
        if not payload.chat or not payload.chat.phone:
            return {"status": "ignorado", "motivo": "sem_telefone"}

        telefone_raw = payload.chat.phone

        if cls._eh_grupo_ou_canal(payload, telefone_raw):
            logger.info(f"[WEBHOOK] 🛑 Mensagem de grupo/canal ignorada ({telefone_raw}).")
            return {"status": "ignorado", "motivo": "mensagem_de_grupo_ou_canal"}

        if payload.message and getattr(payload.message, "fromMe", False):
            return await cls._processar_mensagem_enviada(payload, telefone_raw)

        if not payload.message:
            return {"status": "ignorado", "motivo": "evento_sem_mensagem"}

        tem_texto = bool(payload.message.text and payload.message.text.strip())
        tem_midia = bool(payload.message.fileURL or payload.message.messageType or payload.message.content)
        if not tem_texto and not tem_midia:
            return {"status": "ignorado", "motivo": "conteudo_vazio"}

        telefone = normalizar_telefone(telefone_raw)
        if not telefone or len("".join(filter(str.isdigit, telefone))) < 8:
            return {"status": "ignorado", "motivo": "telefone_invalido"}

        nome_contato = payload.chat.name or payload.message.senderName or "Desconhecido"

        if settings.SANDBOX_MODE:
            apenas_digitos = "".join(filter(str.isdigit, telefone))
            if not apenas_digitos.endswith(settings.WHITELIST_PHONE_SUFFIX):
                logger.info(f"[SEGURANÇA] 🛑 Mensagem de {telefone} ignorada (fora da whitelist de teste).")
                return {"status": "ignorado", "motivo": "numero_fora_da_whitelist_de_teste"}

        dados_msg = payload.message.model_dump(mode="json")
        timestamp_disparo = await cls.buffer_gateway.adicionar_mensagem(
            telefone, json.dumps(dados_msg, default=str)
        )

        spawn_background_task(
            InboundService.processar_debounce(telefone, nome_contato, timestamp_disparo),
            name=f"debounce_{telefone}",
        )

        return {"status": "enfileirado_com_debounce", "telefone": telefone}

