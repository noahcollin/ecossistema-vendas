import asyncio
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from core.background import spawn_background_task
from core.database import AsyncSessionLocal
from core.logger import logger
from core.config import settings
from core.temporal import BusinessHoursPolicy
from core.utils import higienizar_nome_perfil
from core.protocols import WhatsAppGatewayProtocol, CacheBufferProtocol
from repositories.lead_repository import LeadRepository
from services.lead import LeadService
from services.cadence import FollowupService
from services.handover import TransbordoService
from services.pacing import ConversationPacingService
from services.settings import SettingsService
from services.inbound.optout import OptOutGuard
from services.inbound.failover import InboundFailoverService
from services.inbound.consolidation import MessageConsolidator, default_message_consolidator
from integrations.uazapi.gateway import default_uazapi_gateway
from integrations.redis.gateway import default_redis_buffer_gateway
import agents
import models


class InboundService:
    """
    Orquestrador de Conversação Inbound (Clean Application Service).
    Segue rigorosamente os princípios SOLID:
    - SRP: Orquestra o ciclo de vida da mensagem; delega consolidação, pacing, opt-out e failover.
    - DIP: Injeta gateways de WhatsApp, Buffer e Consolidadores desacoplados.
    - OCP: Políticas de pacing, horário comercial, Kill-Switch e modelos configuráveis em tempo real.
    """

    whatsapp_gateway: WhatsAppGatewayProtocol = default_uazapi_gateway
    buffer_gateway: CacheBufferProtocol = default_redis_buffer_gateway
    message_consolidator: MessageConsolidator = default_message_consolidator

    SEMAFORO_CONCORRENCIA_IA = asyncio.Semaphore(settings.CONCURRENCY_SEMAPHORE_LIMIT)

    @classmethod
    async def processar_debounce(cls, telefone: str, nome_contato: str, timestamp_disparo: str | float) -> None:
        """Ponto de entrada assíncrono acionado pelo Webhook pós-debounce com serialização por telefone."""
        try:
            cfg = SettingsService.obter_cache_memoria()
            janela_debounce = float(cfg.debounce_segundos or settings.DEBOUNCE_SECONDS)
            await asyncio.sleep(janela_debounce)

            chave_lock = f"lock:inbound:{telefone}"
            token_lock = None
            for _ in range(15):
                eh_ultima = await cls.buffer_gateway.verificar_se_e_ultima(telefone, timestamp_disparo)
                if not eh_ultima:
                    logger.info(f"[DEBOUNCE] ⏳ Nova mensagem detectada para {telefone}. Descartando lote anterior.")
                    return
                token_lock = await cls.buffer_gateway.adquirir_lock(chave_lock, ttl_segundos=60)
                if token_lock:
                    break
                logger.info(f"[INBOUND LOCK] 🔒 Processamento ativo em curso para {telefone}. Aguardando liberação do turno anterior...")
                await asyncio.sleep(1.5)

            if not token_lock:
                logger.warning(f"[INBOUND LOCK] ⚠️ Timeout aguardando liberação de lock para {telefone}.")
                return

            try:
                logger.info(
                    f"[DEBOUNCE] 🚀 Cliente {telefone} parou de digitar por {janela_debounce}s. "
                    f"Consolidando lote completo..."
                )

                texto_consolidado = await cls._consolidar_mensagens_buffer(telefone)
                if not texto_consolidado:
                    logger.info(f"[DEBOUNCE] Nenhuma mensagem válida com conteúdo para processar de {telefone}")
                    return

                async with AsyncSessionLocal() as db:
                    await cls._executar_pipeline_atendimento(db, telefone, nome_contato, texto_consolidado)
            finally:
                await cls.buffer_gateway.liberar_lock(chave_lock, token_lock)

        except Exception as e:
            logger.error(f"[INBOUND ERRO] ❌ Falha crítica no processamento de {telefone}: {e}", exc_info=True)

    @classmethod
    async def _consolidar_mensagens_buffer(cls, telefone: str) -> Optional[str]:
        """Delega a consolidação e normalização de mensagens multimídia para o MessageConsolidator (SRP)."""
        return await cls.message_consolidator.consolidar_buffer(telefone)

    @classmethod
    async def _obter_ou_criar_lead(
        cls,
        db: AsyncSession,
        telefone: str,
        nome_contato: str
    ) -> models.Lead:
        """Busca o lead pelo telefone canônico ou cria novo registro Inbound."""
        lead = await LeadRepository.get_by_phone(db, telefone)
        nome_validado = higienizar_nome_perfil(nome_contato)
        nome_salvar = nome_validado or (nome_contato if nome_contato != "Desconhecido" else None)

        if not lead:
            lead = await LeadRepository.create(
                db=db,
                telefone=telefone,
                nome=nome_salvar,
                tipo_entrada=models.TipoEntradaLead.INBOUND,
                origem_canal="WHATSAPP_DIRETO",
                etapa_funil=models.EtapaFunil.NOVO_CONTATO,
                desfecho=models.DesfechoLead.EM_ANDAMENTO,
                controle=models.ControleAtendimento.PILOTO_IA,
                temperatura=models.TemperaturaLead.FRIO
            )
            logger.info(f"[LEAD NOVO] ✨ Novo lead cadastrado: {telefone} ({nome_salvar or 'Sem nome'}) | Entrada: INBOUND")
        else:
            if nome_validado and (not lead.nome or lead.nome == "Desconhecido"):
                lead.nome = nome_validado
                await db.commit()
                logger.info(f"[LEAD NOME] 🏷️ Nome do lead atualizado no banco: {nome_validado}")

        return lead

    @classmethod
    async def _executar_pipeline_atendimento(
        cls,
        db: AsyncSession,
        telefone: str,
        nome_contato: str,
        texto_consolidado: str
    ) -> None:
        """Orquestra as verificações de segurança, Kill-Switch, persistência e cognição do lead."""
        lead = await cls._obter_ou_criar_lead(db, telefone, nome_contato)

        if lead.opt_out:
            logger.info(f"[LGPD OPT-OUT] 🛑 Mensagem de {telefone} ignorada pois o cliente está descadastrado.")
            return

        if OptOutGuard.verificar_comando(texto_consolidado):
            await OptOutGuard.executar_optout(db, lead, telefone, texto_consolidado, cls.whatsapp_gateway)
            return

        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=texto_consolidado
        )

        await FollowupService.cancelar_followups_pendentes(db, lead.id)

        # 🛡️ GOVERNANÇA GLOBAL: Kill-Switch da Sala de Máquinas
        cfg_operacao = SettingsService.obter_cache_memoria()
        if cfg_operacao.ia_silenciada_global:
            logger.warning(
                f"[KILL-SWITCH GLOBAL ATIVO] 🛡️ Mensagem de {telefone} persistida com segurança. "
                f"Resposta autônoma pausada pelo gestor."
            )
            return

        # 🕒 GOVERNANÇA DE JANELA RECEPTIVA: Modo 24/7 vs. Estrito ao Horário Comercial
        if not cfg_operacao.modo_24h_inbound and not BusinessHoursPolicy.esta_em_horario_comercial():
            await FollowupService.agendar_proximo_followup(db, lead)
            logger.info(
                f"[JANELA RECEPTIVA] 🌙 Mensagem de {telefone} recebida fora do expediente (Modo 24h desativado). "
                f"Retorno programado automaticamente para a abertura do horário comercial."
            )
            return

        if lead.controle in [models.ControleAtendimento.TRANSBORDO_SOLICITADO, models.ControleAtendimento.HUMANO_ASSUMIU]:
            retomou = await TransbordoService.verificar_e_executar_retomada_automatica(db, lead)
            if not retomou:
                logger.info(
                    f"[TRANSBORDO HUMANO ATIVO] 👤 Mensagem de {telefone} arquivada. "
                    f"IA em pausa dentro da janela de intervenção humana ({lead.controle.value})."
                )
                return
            logger.info(
                f"[AUTO-RETOMADA IA] 🤖 Timeout de inatividade humana atingido para {telefone}. "
                f"Controle devolvido para PILOTO_IA. A IA responderá ao lead."
            )

        await cls.whatsapp_gateway.enviar_presenca(telefone, presenca="composing", delay_ms=25000)

        historico_recente = await LeadRepository.get_recent_interactions(
            db=db,
            lead_id=lead.id,
            limit=settings.JANELA_HISTORICO_RECENTE
        )

        async with cls.SEMAFORO_CONCORRENCIA_IA:
            await cls._processar_cognicao_e_resposta(
                db=db,
                lead=lead,
                telefone=telefone,
                nome_contato=nome_contato,
                texto_consolidado=texto_consolidado,
                historico_recente=historico_recente
            )

    @classmethod
    async def _processar_cognicao_e_resposta(
        cls,
        db: AsyncSession,
        lead: models.Lead,
        telefone: str,
        nome_contato: str,
        texto_consolidado: str,
        historico_recente: List[models.Interacao]
    ) -> None:
        """Executa a cognição dos agentes de IA (Analista e Closer), respeitando o Guardião de Velocidade."""
        lead_id = getattr(lead, "id")
        analise = await agents.analisar_lead_e_fsm(
            lead=lead,
            historico_recente=historico_recente,
            nova_mensagem=texto_consolidado
        )

        if analise.opt_out_detectado:
            lead.opt_out = True
            lead.desfecho = models.DesfechoLead.PERDIDO
            lead.motivo_perda = "Descadastro / Opt-out LGPD"
            await db.commit()

            despedida = OptOutGuard.MENSAGEM_CONFIRMACAO
            await LeadRepository.add_interaction(db, lead_id, models.InteracaoOrigem.IA, despedida)
            await cls.whatsapp_gateway.enviar_mensagem(telefone, despedida, delay_ms=1000)
            logger.info(f"[LGPD OPT-OUT] 🛑 Lead {telefone} descadastrado com sucesso.")
            return

        if analise.origem_canal_detectada:
            if not lead.origem_canal or lead.origem_canal == "WHATSAPP_DIRETO":
                lead.origem_canal = analise.origem_canal_detectada

        etapa_anterior = lead.etapa_funil
        desfecho_anterior = lead.desfecho

        if analise.etapa_sugerida != etapa_anterior:
            await ConversationPacingService.resetar_etapa(lead_id)

        lead.etapa_funil = analise.etapa_sugerida
        lead.desfecho = analise.desfecho_sugerido
        lead.temperatura = analise.temperatura_sugerida
        lead.resumo_perfil = analise.resumo_perfil
        lead.dados_qualificacao = (
            analise.dados_qualificacao.model_dump()
            if hasattr(analise.dados_qualificacao, "model_dump")
            else analise.dados_qualificacao
        )

        # Higieniza motivo_perda legado caso o lead retome negociação ativa ou converta em GANHO
        if analise.desfecho_sugerido in [models.DesfechoLead.EM_ANDAMENTO, models.DesfechoLead.GANHO]:
            lead.motivo_perda = None
        elif analise.motivo_perda:
            lead.motivo_perda = analise.motivo_perda

        if analise.valor_estimado is not None:
            lead.valor_estimado = analise.valor_estimado
        if analise.tags_sugeridas:
            LeadRepository.sincronizar_tags(lead, adicionar=analise.tags_sugeridas)

        transbordo_fechamento_pendente = False
        if analise.transbordo_sugerido:
            motivo_analise = (analise.justificativa or "").lower()
            eh_fechamento = bool(
                getattr(analise, "pronto_fechamento", False)
                or (
                    lead.etapa_funil == models.EtapaFunil.FECHAMENTO
                    and any(
                        t in motivo_analise
                        for t in ("fechamento", "contrato", "dados", "diagnóstico", "diagnostico", "reunião", "reuniao", "agendad", "eduardo")
                    )
                )
            )
            if eh_fechamento:
                transbordo_fechamento_pendente = True
            else:
                await TransbordoService.executar_transbordo(
                    db=db,
                    lead=lead,
                    motivo=analise.justificativa,
                    analise=analise
                )
                spawn_background_task(
                    cls.disparar_auditoria_background(lead_id),
                    name=f"auditoria_transbordo_{lead_id}",
                )
                logger.warning(f"[TRANSBORDO ACIONADO] 🛑 Lead {telefone} em transbordo. IA silenciada.")
                return

        desfecho_mudou_para_fechado = (
            analise.desfecho_sugerido in [models.DesfechoLead.GANHO, models.DesfechoLead.PERDIDO]
            and (desfecho_anterior != analise.desfecho_sugerido or not lead.dossie_comercial)
        )
        # Persiste o novo estado da FSM ANTES de disparar tasks de auditoria em sessão paralela
        await db.commit()
        if desfecho_mudou_para_fechado:
            spawn_background_task(
                cls.disparar_auditoria_background(lead_id),
                name=f"auditoria_fechamento_{lead_id}",
            )

        nome_ia = str(lead.nome or nome_contato or "Cliente")
        pacing_eval = await ConversationPacingService.avaliar_e_incrementar(
            lead_id=lead_id,
            etapa=lead.etapa_funil,
            nome_cliente=nome_ia
        )

        cfg_operacao = SettingsService.obter_cache_memoria()

        if pacing_eval.deve_encerrar_por_estagnacao:
            lead.desfecho = models.DesfechoLead.PERDIDO
            lead.temperatura = models.TemperaturaLead.FRIO
            lead.motivo_perda = f"Estagnação Conversacional ({pacing_eval.mensagens_na_etapa} msgs em {lead.etapa_funil.value})"
            await db.commit()

            despedida_humana = (
                cfg_operacao.mensagem_inatividade
                or pacing_eval.mensagem_despedida_humana
                or OptOutGuard.MENSAGEM_CONFIRMACAO
            )
            await LeadRepository.add_interaction(db, lead_id, models.InteracaoOrigem.IA, despedida_humana)
            await cls.whatsapp_gateway.enviar_mensagem(telefone, despedida_humana, delay_ms=1000)
            await FollowupService.cancelar_followups_pendentes(db, lead_id, models.StatusFollowup.ABORTADO)
            spawn_background_task(
                cls.disparar_auditoria_background(lead_id),
                name=f"auditoria_estagnacao_{lead_id}",
            )
            logger.warning(
                f"[PACING GUARD - ESTAGNAÇÃO] 🛑 Lead {telefone} atingiu {pacing_eval.mensagens_na_etapa} mensagens em {lead.etapa_funil.value}. "
                f"Encerrado com despedida humana e desfecho PERDIDO (Zero-Touch)."
            )
            return

        ficha_resumo = str(lead.resumo_perfil) if lead.resumo_perfil else None
        resposta_ia = await agents.gerar_resposta_vendedor(
            nome_cliente_bruto=nome_ia,
            ficha_resumo=ficha_resumo,
            etapa_funil=lead.etapa_funil,
            historico_recente=historico_recente,
            diretriz_proatividade=pacing_eval.diretriz_proatividade
        )

        if not resposta_ia or not resposta_ia.strip():
            await InboundFailoverService.lidar_com_falha_geracao(
                db=db,
                lead=lead,
                telefone=telefone,
                analise=analise
            )
            return

        lead = await LeadRepository.recarregar_lead(db, lead.id) or lead
        if (
            lead.controle in [models.ControleAtendimento.HUMANO_ASSUMIU, models.ControleAtendimento.TRANSBORDO_SOLICITADO]
            or lead.opt_out
            or SettingsService.esta_ia_silenciada()
        ):
            logger.warning(
                f"[COLISAO EM VOO EVITADA] 🛑 Disparo da IA cancelado para {telefone}. "
                f"Controle: {lead.controle.value} | Opt-out: {lead.opt_out} | Kill-Switch: {SettingsService.esta_ia_silenciada()}."
            )
            return

        partes_mensagem, _ = await cls.whatsapp_gateway.enviar_mensagem_humanizada(
            telefone=telefone,
            texto_bruto=resposta_ia,
            delay_base_ms=cfg_operacao.pacing.delay_base_ms,
            simular_digitacao=cfg_operacao.pacing.simular_digitacao,
            intervalo_entre_baloes=cfg_operacao.pacing.intervalo_entre_baloes_seg,
        )

        texto_historico = "\n\n".join(partes_mensagem) if partes_mensagem else resposta_ia
        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.IA,
            texto=texto_historico
        )

        logger.info(
            f"[CICLO COMPLETO] ✅ Atendimento finalizado com sucesso para {telefone} "
            f"({len(partes_mensagem)} balão(ões) enviado(s) | Etapa: {lead.etapa_funil.value})"
        )

        if transbordo_fechamento_pendente:
            motivo_fechamento = analise.justificativa or "Reunião de Diagnóstico Agendada com o Eduardo"
            await TransbordoService.executar_transbordo(
                db=db,
                lead=lead,
                motivo=motivo_fechamento,
                analise=analise
            )
            spawn_background_task(
                cls.disparar_auditoria_background(lead_id),
                name=f"auditoria_fechamento_transbordo_{lead_id}",
            )
            logger.info(
                f"[TRANSBORDO FECHAMENTO] 🤝 Mensagem de acolhimento enviada para {telefone}. "
                f"Atendimento escalado para formalização e assinatura de contrato pela equipe humana."
            )
            return

        await FollowupService.agendar_proximo_followup(db, lead)

    @staticmethod
    def dividir_mensagens_whatsapp(texto: str) -> list[str]:
        """Delega para a função utilitária pura centralizada em core.utils (compatibilidade)."""
        from core.utils import dividir_mensagens_whatsapp as _dividir
        return _dividir(texto)

    @classmethod
    def _verificar_comando_optout_deterministico(cls, texto: str) -> bool:
        """Delega para o OptOutGuard (compatibilidade com testes legados)."""
        return OptOutGuard.verificar_comando(texto)

    @classmethod
    async def _executar_optout_deterministico(
        cls,
        db: AsyncSession,
        lead: models.Lead,
        telefone: str,
        texto_recebido: str
    ) -> None:
        """Delega para o OptOutGuard (compatibilidade com testes legados)."""
        await OptOutGuard.executar_optout(db, lead, telefone, texto_recebido, cls.whatsapp_gateway)

    @staticmethod
    async def disparar_auditoria_background(lead_id: int) -> None:
        """Executa a auditoria em background sem bloquear a resposta no WhatsApp."""
        try:
            async with AsyncSessionLocal() as bg_db:
                await LeadService.gerar_dossie_lead(bg_db, lead_id)
        except Exception as exc:
            logger.error(f"[AUDITOR BACKGROUND ERRO] Falha ao gerar dossiê para Lead ID {lead_id}: {exc}")
