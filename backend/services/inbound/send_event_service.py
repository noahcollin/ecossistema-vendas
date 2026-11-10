"""
Serviço de Ingestão, Polling e Processamento de Eventos do Send Inteligentte (API Oficial Meta).
Suporta operação híbrida (Polling `GET /events` + Webhook `POST /webhooks/send`) com
deduplicação idempotente por `event.id`, tratamento de `conversation.handover` e `optedOut`.
"""

import asyncio
import hashlib
import hmac
import os
import time
from collections import deque
from typing import Any, Callable
from contextlib import AbstractAsyncContextManager
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import AsyncSessionLocal
from core.logger import logger
from core.protocols import CacheBufferProtocol
from core.utils import normalizar_telefone
from integrations.redis.buffer import redis_client
from integrations.redis.gateway import default_redis_buffer_gateway
from integrations.send_inteligentte.client import buscar_eventos_send
from repositories.lead_repository import LeadRepository
from services.cadence import FollowupService
from services.inbound.webhook_service import WebhookApplicationService
import models
import schemas


class SendEventService:
    """
    Orquestra o recebimento de eventos do Send Inteligentte (Polling e Webhook),
    garantindo idempotência, sincronização de handover humano e proteção de opt-out.
    """

    buffer_gateway: CacheBufferProtocol = default_redis_buffer_gateway
    session_factory: Callable[[], AbstractAsyncContextManager[AsyncSession]] = AsyncSessionLocal
    _processed_memory_ids: deque[str] = deque(maxlen=5000)

    @staticmethod
    def verificar_assinatura_webhook(
        raw_body: bytes,
        timestamp: str | None,
        signature: str | None,
        secret: str | None = None,
    ) -> bool:
        """
        Valida a assinatura HMAC-SHA256 do Send Inteligentte conforme Seção 4.3 da especificação:
        expected = 'sha256=' + hmac.new(secret, f'{timestamp}.' + raw_body, sha256).hexdigest()
        """
        segredo = (secret if secret is not None else settings.SEND_WEBHOOK_SECRET or "").strip()
        if not segredo:
            return True

        if not timestamp or not signature:
            return False

        try:
            ts_int = int(timestamp)
        except ValueError:
            return False

        if abs(time.time() - ts_int) > 300:
            logger.warning("[SEND WEBHOOK] 🛑 Assinatura rejeitada: timestamp fora da janela de 5 minutos.")
            return False

        mensagem_assinada = f"{timestamp}.".encode("utf-8") + raw_body
        esperado = "sha256=" + hmac.new(
            segredo.encode("utf-8"),
            mensagem_assinada,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature.strip(), esperado)

    @classmethod
    async def _verificar_e_marcar_processado(cls, event_id: str) -> bool:
        """
        Retorna True se o evento JÁ foi processado anteriormente (duplicata).
        Caso contrário, marca como processado em memória e no Redis (TTL 7 dias) e retorna False.
        """
        if not event_id:
            return False

        if event_id in cls._processed_memory_ids:
            return True

        chave_redis = f"send:event:processed:{event_id}"
        try:
            ja_existe = await redis_client.get(chave_redis)
            if ja_existe:
                cls._processed_memory_ids.append(event_id)
                return True
            await redis_client.setex(chave_redis, 604800, "1")
        except Exception:
            pass

        cls._processed_memory_ids.append(event_id)
        return False

    @classmethod
    async def _processar_handover_externo(cls, data: dict[str, Any]) -> dict[str, Any]:
        """
        Trata o evento `conversation.handover`:
        Um operador humano respondeu pelo Live Chat do Send ou pausou o agente.
        """
        contact = data.get("contact") or {}
        handover = data.get("handover") or {}
        telefone_raw = str(contact.get("phone") or "").strip()
        telefone = normalizar_telefone(telefone_raw)

        if not telefone:
            return {"status": "ignorado", "motivo": "sem_telefone"}

        por = str(handover.get("by") or "human").strip().lower()
        if por == "agent":
            logger.info(
                f"[SEND HANDOVER EVENT] ℹ️ Eco de handover do próprio agente ignorado para {telefone}."
            )
            return {"status": "ignorado_eco_agente", "telefone": telefone}

        # Limpa qualquer buffer de debounce em curso para evitar resposta concorrente
        try:
            await cls.buffer_gateway.obter_e_limpar_buffer(telefone)
        except Exception:
            pass

        operador = handover.get("userName") or "Operador Send"
        motivo = handover.get("reason") or f"Intervenção no Live Chat Send ({por}: {operador})"

        async with cls.session_factory() as db:
            lead = await LeadRepository.get_by_phone(db, telefone)
            if not lead:
                lead = await LeadRepository.create(
                    db=db,
                    telefone=telefone,
                    nome=contact.get("name") or None,
                    tipo_entrada=models.TipoEntradaLead.INBOUND,
                    origem_canal="SEND_INTELIGENTTE",
                    etapa_funil=models.EtapaFunil.NOVO_CONTATO,
                    desfecho=models.DesfechoLead.EM_ANDAMENTO,
                    controle=models.ControleAtendimento.HUMANO_ASSUMIU,
                    temperatura=models.TemperaturaLead.MORNO,
                    tags=["EM_ATENDIMENTO_HUMANO"],
                )
            else:
                lead.controle = models.ControleAtendimento.HUMANO_ASSUMIU
                LeadRepository.sincronizar_tags(
                    lead,
                    adicionar=["EM_ATENDIMENTO_HUMANO"],
                    remover=["REQUER_ATENCAO"],
                )

            await FollowupService.cancelar_followups_pendentes(db, lead.id)
            await LeadRepository.add_interaction(
                db=db,
                lead_id=lead.id,
                origem=models.InteracaoOrigem.SISTEMA,
                texto=f"[HANDOVER SEND INTELIGENTTE] 👤 Agente pausado no Send ({por} - {operador}). Motivo: {motivo}",
            )
            await db.commit()

        logger.info(f"[SEND HANDOVER EVENT] 👤 Lead {telefone} marcado como HUMANO_ASSUMIU ({operador}).")
        return {"status": "handover_sincronizado", "telefone": telefone}

    @classmethod
    async def _processar_optout_externo(
        cls,
        telefone: str,
        nome_contato: str | None,
        texto_gatilho: str,
    ) -> dict[str, Any]:
        """
        Quando `contact.optedOut == True`, o Send Inteligentte já descadastrou o contato.
        Limpamos o buffer imediatamente, marcamos opt_out no banco e NÃO respondemos.
        """
        try:
            await cls.buffer_gateway.obter_e_limpar_buffer(telefone)
        except Exception:
            pass

        async with cls.session_factory() as db:
            lead = await LeadRepository.get_by_phone(db, telefone)
            if not lead:
                lead = await LeadRepository.create(
                    db=db,
                    telefone=telefone,
                    nome=nome_contato if (nome_contato and nome_contato != "Desconhecido") else None,
                    tipo_entrada=models.TipoEntradaLead.INBOUND,
                    origem_canal="SEND_INTELIGENTTE",
                    etapa_funil=models.EtapaFunil.NOVO_CONTATO,
                    desfecho=models.DesfechoLead.PERDIDO,
                    controle=models.ControleAtendimento.PILOTO_IA,
                    temperatura=models.TemperaturaLead.FRIO,
                    tags=["OPT_OUT"],
                )
            lead.opt_out = True
            lead.desfecho = models.DesfechoLead.PERDIDO
            lead.motivo_perda = "Opt-out / Descadastro no Send Inteligentte"
            LeadRepository.sincronizar_tags(lead, adicionar=["OPT_OUT"])

            await FollowupService.cancelar_followups_pendentes(db, lead.id)
            if texto_gatilho:
                await LeadRepository.add_interaction(
                    db=db,
                    lead_id=lead.id,
                    origem=models.InteracaoOrigem.CLIENTE,
                    texto=f"[OPT-OUT SEND] {texto_gatilho}",
                )
            await db.commit()

        logger.info(f"[SEND OPT-OUT] 🛑 Contato {telefone} marcou opt-out no Send. Silêncio absoluto aplicado.")
        return {"status": "opt_out_processado", "telefone": telefone}

    @classmethod
    async def _processar_mensagem_recebida(cls, data: dict[str, Any]) -> dict[str, Any]:
        """
        Converte `message.received` do Send Inteligentte para o pipeline canônico
        (Debounce + MediaPipeline + FSM + Eli Gentil).
        """
        contact = data.get("contact") or {}
        message = data.get("message") or {}
        origin = data.get("origin") or {}

        telefone_raw = str(contact.get("phone") or "").strip()
        if not telefone_raw:
            return {"status": "ignorado", "motivo": "sem_telefone"}

        telefone = normalizar_telefone(telefone_raw)
        nome_contato = (contact.get("name") or "").strip() or "Desconhecido"

        msg_type = (message.get("type") or "text").lower()
        btn = message.get("button") or {}
        texto_extraido = (
            message.get("text")
            or btn.get("text")
            or btn.get("payload")
            or ""
        ).strip()

        # Se o próprio evento já sinaliza optedOut=True, descadastra sem responder!
        if contact.get("optedOut") is True:
            return await cls._processar_optout_externo(telefone, nome_contato, texto_extraido)

        # Se veio de campanha do Send Inteligentte, registra o canal de origem no lead caso já exista
        if isinstance(origin, dict) and (origin.get("campaignName") or origin.get("templateName")):
            campanha_nome = origin.get("campaignName") or origin.get("templateName")
            try:
                async with cls.session_factory() as db_orig:
                    lead_orig = await LeadRepository.get_by_phone(db_orig, telefone)
                    if lead_orig and (not lead_orig.origem_canal or lead_orig.origem_canal == "WHATSAPP_DIRETO"):
                        lead_orig.origem_canal = f"SEND_CAMPANHA:{campanha_nome}"[:100]
                        await db_orig.commit()
            except Exception:
                pass

        # Mapeia para UazapiMessage compatível com MediaPipeline e WebhookApplicationService
        if msg_type in ("audio", "voice", "ptt", "image", "sticker", "video", "document"):
            media_id = str(message.get("mediaId") or message.get("id") or "")
            uazapi_msg = schemas.UazapiMessage(
                id=media_id,
                messageid=media_id,
                fromMe=False,
                isGroup=False,
                text=texto_extraido,
                senderName=nome_contato,
                messageType=msg_type,
                content={"mimetype": message.get("mimeType") or ""},
            )
        else:
            msg_id = str(message.get("wamid") or message.get("id") or "")
            uazapi_msg = schemas.UazapiMessage(
                id=msg_id,
                messageid=msg_id,
                fromMe=False,
                isGroup=False,
                text=texto_extraido,
                senderName=nome_contato,
                messageType="text",
            )

        payload_uazapi = schemas.UazapiPayload(
            event="message.received",
            instanceName="send_inteligentte",
            chat=schemas.UazapiChat(
                name=nome_contato,
                phone=telefone,
                isGroup=False,
            ),
            message=uazapi_msg,
        )

        return await WebhookApplicationService.processar_evento_uazapi(payload_uazapi)

    @classmethod
    async def processar_evento_send(cls, evento: dict[str, Any]) -> dict[str, Any]:
        """
        Processa um envelope de evento do Send Inteligentte (vindo do Polling ou do Webhook).
        Envelope: {id, seq, type, version, createdAt, data}
        """
        if not isinstance(evento, dict):
            return {"status": "ignorado", "motivo": "formato_invalido"}

        event_type = str(evento.get("type") or "").strip()
        event_id = str(evento.get("id") or "").strip()

        if event_type == "ping":
            return {"status": "ok", "type": "ping"}

        if event_id and await cls._verificar_e_marcar_processado(event_id):
            logger.debug(f"[SEND EVENT] 🔄 Evento {event_id} (seq={evento.get('seq')}) já processado. Ignorando.")
            return {"status": "ignorado", "motivo": "evento_duplicado", "id": event_id}

        data = evento.get("data") or {}
        if event_type == "conversation.handover":
            return await cls._processar_handover_externo(data)

        if event_type == "message.received":
            return await cls._processar_mensagem_recebida(data)

        logger.info(f"[SEND EVENT] ℹ️ Tipo de evento desconhecido ignorado: {event_type}")
        return {"status": "ignorado", "motivo": f"tipo_nao_suportado:{event_type}"}

    @classmethod
    async def carregar_cursor(cls) -> int:
        """Recupera o maior `seq` processado entre o Redis e o arquivo local de fallback."""
        maior_cursor = 15
        try:
            val_redis = await redis_client.get("send:events:cursor")
            if val_redis is not None and str(val_redis).strip().isdigit():
                maior_cursor = max(maior_cursor, int(str(val_redis).strip()))
        except Exception:
            pass

        caminhos = [
            settings.SEND_CURSOR_FILE,
            os.path.join(os.path.dirname(__file__), "..", "..", settings.SEND_CURSOR_FILE),
            os.path.join(os.path.dirname(__file__), "..", "..", "..", settings.SEND_CURSOR_FILE),
        ]
        for caminho in caminhos:
            if caminho and os.path.exists(caminho):
                try:
                    with open(caminho, "r", encoding="utf-8") as f:
                        conteudo = f.read().strip()
                        if conteudo.isdigit():
                            maior_cursor = max(maior_cursor, int(conteudo))
                except Exception:
                    pass
        return maior_cursor

    @classmethod
    async def salvar_cursor(cls, cursor: int) -> None:
        """Persiste o cursor `seq` no Redis e no arquivo local para tolerância a reinicializações."""
        try:
            await redis_client.set("send:events:cursor", str(cursor))
        except Exception:
            pass

        caminho = settings.SEND_CURSOR_FILE
        if caminho:
            try:
                with open(caminho, "w", encoding="utf-8") as f:
                    f.write(str(cursor))
            except Exception:
                pass

    @classmethod
    async def worker_loop(cls) -> None:
        """
        Loop contínuo de Polling (`GET /api/v1/events`) em background.
        Opera automaticamente sempre que `SEND_API_KEY` estiver configurada.
        """
        if not settings.SEND_API_KEY:
            logger.info("[SEND POLLER] ℹ️ SEND_API_KEY não configurada. Worker de polling Send em standby.")
            return

        after = await cls.carregar_cursor()
        logger.info(f"[SEND POLLER] 🚀 Worker Send Inteligentte iniciado (cursor inicial after={after}).")

        while True:
            try:
                if not settings.SEND_API_KEY:
                    await asyncio.sleep(10.0)
                    continue

                resposta = await buscar_eventos_send(after=after, limit=50)
                eventos = resposta.get("events") or []
                next_after = resposta.get("nextAfter", after)
                has_more = bool(resposta.get("hasMore", False))

                if eventos:
                    logger.info(
                        f"[SEND POLLER] 📥 Recebidos {len(eventos)} evento(s) do Send Inteligentte "
                        f"(seq {after} -> {next_after})."
                    )
                    # Pré-filtro de lote: identifica telefones que sofreram handover ou opt-out mais adiante no mesmo lote
                    ultimo_bloqueio_seq: dict[str, int] = {}
                    for ev in eventos:
                        ev_seq = int(ev.get("seq") or 0)
                        ev_type = str(ev.get("type") or "")
                        ev_data = ev.get("data") or {}
                        ev_contact = ev_data.get("contact") or {}
                        ev_handover = ev_data.get("handover") or {}
                        ev_phone = normalizar_telefone(str(ev_contact.get("phone") or ""))
                        eh_handover_humano = (
                            ev_type == "conversation.handover"
                            and str(ev_handover.get("by") or "human").strip().lower() != "agent"
                        )
                        if ev_phone and (eh_handover_humano or ev_contact.get("optedOut") is True):
                            ultimo_bloqueio_seq[ev_phone] = max(ultimo_bloqueio_seq.get(ev_phone, 0), ev_seq)

                    for ev in eventos:
                        try:
                            ev_seq = int(ev.get("seq") or 0)
                            ev_type = str(ev.get("type") or "")
                            ev_data = ev.get("data") or {}
                            ev_contact = ev_data.get("contact") or {}
                            ev_phone = normalizar_telefone(str(ev_contact.get("phone") or ""))
                            if (
                                ev_type == "message.received"
                                and not ev_contact.get("optedOut")
                                and ev_phone in ultimo_bloqueio_seq
                                and ev_seq < ultimo_bloqueio_seq[ev_phone]
                            ):
                                logger.info(
                                    f"[SEND POLLER] ⏭️ Mensagem seq={ev_seq} de {ev_phone} ignorada "
                                    f"(há handover/opt-out posterior seq={ultimo_bloqueio_seq[ev_phone]} no lote)."
                                )
                                continue
                            await cls.processar_evento_send(ev)
                        except Exception as ev_err:
                            logger.error(f"[SEND POLLER ERRO] Falha ao processar evento {ev.get('id')}: {ev_err}")

                if isinstance(next_after, int) and next_after != after:
                    after = next_after
                    await cls.salvar_cursor(after)

                if has_more:
                    await asyncio.sleep(0.2)
                else:
                    await asyncio.sleep(max(1.0, float(settings.SEND_POLL_INTERVAL_SECONDS)))

            except asyncio.CancelledError:
                logger.info("[SEND POLLER] 🛑 Worker Send Inteligentte encerrado graciosamente.")
                break
            except Exception as err:
                logger.error(f"[SEND POLLER ERRO] ⚠️ Erro no loop de polling do Send: {err}")
                await asyncio.sleep(5.0)

