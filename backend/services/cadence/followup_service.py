import asyncio
import random
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import logger
from core.config import settings
from core.database import AsyncSessionLocal
from core.temporal import BusinessHoursPolicy
import models
from core.protocols import WhatsAppGatewayProtocol
from repositories.lead_repository import LeadRepository
from repositories.followup_repository import FollowupRepository
from integrations.uazapi.gateway import default_uazapi_gateway
from integrations.redis.buffer import redis_client
from agents import gerar_mensagem_followup, auditar_jornada_lead


class FollowupService:
    """
    Motor de Cadência Temporal e Follow-Up Ativo (Fase 2 do PRD - RF11 e RF12).
    Orquestra o agendamento proativo, cancelamento reativo e disparo inteligente
    com blindagem anti-ban e adequação comercial.
    """

    whatsapp_gateway: WhatsAppGatewayProtocol = default_uazapi_gateway

    # Delegação para a política isolada de horários comerciais e anti-ban jitter
    ajustar_para_horario_comercial = BusinessHoursPolicy.ajustar_para_horario_comercial
    calcular_data_agendamento = BusinessHoursPolicy.calcular_momento_disparo

    @classmethod
    async def agendar_proximo_followup(
        cls,
        db: AsyncSession,
        lead: models.Lead
    ) -> Optional[models.FollowupAgendado]:
        """Programa o próximo toque da cadência temporal (RF11)."""
        if not settings.FOLLOWUP_ENABLED:
            return None

        # Checagem de elegibilidade
        if (
            lead.opt_out
            or lead.desfecho != models.DesfechoLead.EM_ANDAMENTO
            or lead.controle != models.ControleAtendimento.PILOTO_IA
            or (lead.etapa_funil == models.EtapaFunil.FECHAMENTO and lead.desfecho == models.DesfechoLead.GANHO)
        ):
            await FollowupRepository.cancelar_pendentes_por_lead(db, lead.id, models.StatusFollowup.ABORTADO)
            return None

        # Se já existe follow-up pendente, preserva
        pendente = await FollowupRepository.obter_pendente_por_lead(db, lead.id)
        if pendente:
            return pendente

        # Avalia a próxima tentativa baseada no histórico
        ultima_tentativa = await FollowupRepository.obter_ultima_tentativa(db, lead.id)
        proxima_tentativa = 1

        if ultima_tentativa and ultima_tentativa.status == models.StatusFollowup.DISPARADO:
            if ultima_tentativa.tentativa >= 3:
                # Esgotamento de 3 toques -> Congela cadência (FSM Seção 5.1)
                lead.desfecho = models.DesfechoLead.CONGELADO_CADENCIA
                lead.temperatura = models.TemperaturaLead.FRIO
                lead.motivo_perda = "Cadência Esgotada (Sem Resposta após 3 Toques)"
                await db.commit()

                logger.warning(f"[CADENCIA] ❄️ Lead {lead.telefone} esgotou 3 toques. FSM: CONGELADO_CADENCIA.")
                asyncio.create_task(cls.disparar_auditoria_em_segundo_plano(lead.id))
                return None
            else:
                proxima_tentativa = ultima_tentativa.tentativa + 1

        agendado_para = cls.calcular_data_agendamento(proxima_tentativa)
        novo_followup = await FollowupRepository.criar(
            db=db,
            lead_id=lead.id,
            etapa_funil=lead.etapa_funil,
            tentativa=proxima_tentativa,
            agendado_para=agendado_para
        )

        logger.info(
            f"[CADENCIA] 📅 Toque {proxima_tentativa}/3 agendado para {lead.telefone} "
            f"em {agendado_para.strftime('%d/%m/%Y %H:%M:%S UTC')}."
        )
        return novo_followup

    @staticmethod
    async def cancelar_followups_pendentes(
        db: AsyncSession,
        lead_id: int,
        motivo: models.StatusFollowup = models.StatusFollowup.CANCELADO_POR_RESPOSTA
    ) -> int:
        """Cancela atômica e imediatamente todos os follow-ups pendentes do lead (RF12)."""
        qtd = await FollowupRepository.cancelar_pendentes_por_lead(db, lead_id, motivo)
        if qtd > 0:
            logger.info(f"[CADENCIA] 🛑 {qtd} follow-up(s) cancelado(s) para Lead ID {lead_id} (RF12).")
        return qtd

    @staticmethod
    async def listar_por_lead(
        db: AsyncSession,
        lead_id: int
    ) -> List[models.FollowupAgendado]:
        """Lista todos os agendamentos de follow-up (cadência temporal) do lead."""
        return await FollowupRepository.listar_por_lead(db, lead_id)

    @classmethod
    async def _executar_disparo_individual(
        cls,
        db: AsyncSession,
        f_item: models.FollowupAgendado
    ) -> bool:
        """Executa a formulação da mensagem contextual e o envio para um lead específico."""
        # 🔒 Trava atômica distribuída no Redis (Anti-Duplo Disparo / Concorrência de Workers)
        chave_lock = f"lock:followup:{f_item.id}"
        adquiriu_lock = await redis_client.set(chave_lock, "1", nx=True, ex=180)
        if not adquiriu_lock:
            logger.warning(
                f"[CADENCIA LOCK] 🔒 Follow-up ID {f_item.id} já está sendo processado por outro worker concorrente. Ignorando."
            )
            return False

        try:
            lead = f_item.lead if (hasattr(f_item, "lead") and f_item.lead is not None) else await LeadRepository.get_by_id(db, f_item.lead_id)
            if not lead or lead.opt_out or lead.desfecho != models.DesfechoLead.EM_ANDAMENTO or lead.controle != models.ControleAtendimento.PILOTO_IA:
                await FollowupRepository.atualizar_status(db, f_item, models.StatusFollowup.ABORTADO)
                return False

            # 🛡️ GUARDA DE MENSAGENS ATIVAS NO BUFFER DO REDIS:
            # Se o cliente acabou de enviar mensagens que ainda estão no buffer de debounce,
            # aborta o follow-up imediatamente para não parecer incoerente ("Oi, sumiu?").
            qtd_buffer = await redis_client.llen(f"buffer:{lead.telefone}")
            if qtd_buffer > 0:
                logger.info(
                    f"[CADENCIA CANCELADA] 🛑 Lead {lead.telefone} possui {qtd_buffer} mensagem(ns) no buffer do Redis (em debounce). "
                    f"Cancelando follow-up por resposta ativa do cliente."
                )
                await FollowupRepository.atualizar_status(db, f_item, models.StatusFollowup.CANCELADO_POR_RESPOSTA)
                return False

            historico = await LeadRepository.get_recent_interactions(
                db=db,
                lead_id=lead.id,
                limit=settings.JANELA_HISTORICO_RECENTE
            )

            texto_msg = await gerar_mensagem_followup(
                nome_cliente_bruto=lead.nome or "Cliente",
                ficha_resumo=lead.resumo_perfil,
                etapa_funil=f_item.etapa_funil,
                tentativa=f_item.tentativa,
                historico_recente=historico
            )

            if not texto_msg or not texto_msg.strip():
                logger.critical(
                    f"[CADENCIA SILENCIADA] 🚨 Follow-up para lead {lead.telefone} não gerou mensagem (créditos OpenAI ou falha de IA). "
                    f"Abortando follow-up ID {f_item.id} e silenciando disparos automáticos."
                )
                await FollowupRepository.atualizar_status(db, f_item, models.StatusFollowup.ABORTADO)
                try:
                    await redis_client.set("alerta_sistema:openai_sem_creditos", "1", ex=86400)
                except Exception as r_err:
                    logger.warning(f"[CADENCIA REDIS] Falha ao registrar alerta no Redis: {r_err}")
                return False

            # Disparo humanizado em múltiplos balões com digitação (SRP / DRY)
            baloes_enviados, sucesso = await cls.whatsapp_gateway.enviar_mensagem_humanizada(
                telefone=lead.telefone,
                texto_bruto=texto_msg,
                delay_base_ms=1000,
                simular_digitacao=settings.FOLLOWUP_SIMULAR_DIGITACAO
            )
            if not sucesso:
                logger.error(
                    f"[CADENCIA ERRO] ❌ Falha no envio WhatsApp para {lead.telefone}. "
                    f"Abortando follow-up ID {f_item.id} para evitar loops de repetição."
                )
                await FollowupRepository.atualizar_status(db, f_item, models.StatusFollowup.ABORTADO)
                return False

            # Registra interação de IA no histórico de forma limpa (sem |||)
            texto_historico = "\n\n".join(baloes_enviados) if baloes_enviados else texto_msg
            await LeadRepository.add_interaction(db=db, lead_id=lead.id, origem=models.InteracaoOrigem.IA, texto=texto_historico)
            await FollowupRepository.marcar_como_disparado(db, f_item, texto_historico)

            logger.info(
                f"[CADENCIA] 🚀 Toque {f_item.tentativa}/3 disparado com sucesso para {lead.telefone} "
                f"({len(baloes_enviados)} balão(ões))!"
            )
            await cls.agendar_proximo_followup(db, lead)
            return True
        finally:
            await redis_client.delete(chave_lock)

    @classmethod
    async def processar_lote_followups(cls, db: AsyncSession) -> int:
        """Processa a fila de follow-ups vencidos com guardrails de horário e anti-ban pacing."""
        if not settings.FOLLOWUP_ENABLED:
            return 0

        vencidos = await FollowupRepository.obter_vencidos_pendentes(db, limite=20, carregar_lead=True)
        if not vencidos:
            return 0

        agora_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        ajustado = cls.ajustar_para_horario_comercial(agora_utc)

        # Se estamos fora da janela comercial, reprograma o lote com jitter
        if (ajustado - agora_utc).total_seconds() > 60:
            logger.info(f"[CADENCIA] 🌙 Fora do expediente. Reprogramando {len(vencidos)} follow-ups para {ajustado.strftime('%d/%m %H:%M')}.")
            for i, item in enumerate(vencidos):
                item.agendado_para = cls.ajustar_para_horario_comercial(agora_utc, indice_dispersao=i)
            await db.commit()
            return 0

        processados = 0
        for idx, f_item in enumerate(vencidos):
            try:
                sucesso = await cls._executar_disparo_individual(db, f_item)
                if sucesso:
                    processados += 1
                if idx < len(vencidos) - 1:
                    pacing = random.uniform(settings.FOLLOWUP_PACING_MIN_SECONDS, settings.FOLLOWUP_PACING_MAX_SECONDS)
                    await asyncio.sleep(pacing)
            except Exception as e:
                logger.error(f"[CADENCIA ERRO] ❌ Falha ao processar follow-up ID {f_item.id}: {e}", exc_info=True)

        return processados

    @staticmethod
    async def disparar_auditoria_em_segundo_plano(lead_id: int) -> None:
        """Dispara a auditoria do DealAuditorAgent quando a cadência congela."""
        try:
            async with AsyncSessionLocal() as bg_db:
                lead = await LeadRepository.get_by_id(bg_db, lead_id)
                if lead:
                    interacoes = await LeadRepository.get_interactions(bg_db, lead_id)
                    dossie = await auditar_jornada_lead(lead, interacoes)
                    dossie_dict = dossie.model_dump() if hasattr(dossie, "model_dump") else dict(dossie)
                    await LeadRepository.salvar_dossie(bg_db, lead, dossie_dict)
                    logger.info(f"[CADENCIA AUDITORIA] 📋 Dossiê gerado para Lead ID {lead_id} congelado.")
        except Exception as e:
            logger.error(f"[CADENCIA AUDITORIA ERRO] ❌ Falha na auditoria: {e}")

    @classmethod
    async def worker_loop(cls) -> None:
        """Loop contínuo de background polling do motor de cadência."""
        poll_interval = settings.FOLLOWUP_WORKER_POLL_INTERVAL_SECONDS
        logger.info(f"[CADENCIA WORKER] 🟢 Worker ativo (Poll: {poll_interval}s).")

        while True:
            try:
                await asyncio.sleep(poll_interval)
                async with AsyncSessionLocal() as db:
                    await cls.processar_lote_followups(db)
            except asyncio.CancelledError:
                logger.info("[CADENCIA WORKER] 🛑 Worker encerrado graciosamente.")
                break
            except Exception as e:
                logger.error(f"[CADENCIA WORKER ERRO] ❌ Erro inesperado no loop: {e}", exc_info=True)
