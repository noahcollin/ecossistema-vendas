import asyncio
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal
from core.logger import logger
from core.config import settings
from core.utils import higienizar_nome_perfil
from core.protocols import WhatsAppGatewayProtocol, CacheBufferProtocol
from repositories.lead_repository import LeadRepository
from services.lead_service import LeadService
from services.followup_service import FollowupService
from services.transbordo_service import TransbordoService
from services.conversation_pacing_service import ConversationPacingService
from services.optout_guard import OptOutGuard
from services.inbound_failover_service import InboundFailoverService
from services.message_consolidation import MessageConsolidator, default_message_consolidator
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
    - OCP: Políticas de pacing e modelos configuráveis via Twelve-Factor Settings.
    """

    # Injeção de dependências de infraestrutura (DIP) com defaults canônicos
    whatsapp_gateway: WhatsAppGatewayProtocol = default_uazapi_gateway
    buffer_gateway: CacheBufferProtocol = default_redis_buffer_gateway
    message_consolidator: MessageConsolidator = default_message_consolidator

    # Semáforo Global de Concorrência de IA (FinOps / Proteção contra Rate Limits)
    SEMAFORO_CONCORRENCIA_IA = asyncio.Semaphore(settings.CONCURRENCY_SEMAPHORE_LIMIT)

    @classmethod
    async def processar_debounce(cls, telefone: str, nome_contato: str, timestamp_disparo: str | float) -> None:
        """Ponto de entrada assíncrono acionado pelo Webhook pós-debounce."""
        try:
            await asyncio.sleep(settings.DEBOUNCE_SECONDS)

            eh_ultima = await cls.buffer_gateway.verificar_se_e_ultima(telefone, timestamp_disparo)
            if not eh_ultima:
                logger.info(f"[DEBOUNCE] ⏳ Nova mensagem detectada para {telefone}. Descartando lote anterior.")
                return

            logger.info(
                f"[DEBOUNCE] 🚀 Cliente {telefone} parou de digitar por {settings.DEBOUNCE_SECONDS}s. "
                f"Consolidando lote completo..."
            )

            texto_consolidado = await cls._consolidar_mensagens_buffer(telefone)
            if not texto_consolidado:
                logger.info(f"[DEBOUNCE] Nenhuma mensagem válida com conteúdo para processar de {telefone}")
                return

            async with AsyncSessionLocal() as db:
                await cls._executar_pipeline_atendimento(db, telefone, nome_contato, texto_consolidado)

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
        """Orquestra as verificações de segurança, persistência e cognição do lead."""
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
        if analise.motivo_perda:
            lead.motivo_perda = analise.motivo_perda
        if analise.valor_estimado is not None:
            lead.valor_estimado = analise.valor_estimado
        if analise.tags_sugeridas:
            LeadRepository.sincronizar_tags(lead, adicionar=analise.tags_sugeridas)

        transbordo_fechamento_pendente = False
        if analise.transbordo_sugerido:
            motivo_analise = (analise.justificativa or "").lower()
            if lead.etapa_funil == models.EtapaFunil.FECHAMENTO and (
                "fechamento" in motivo_analise or "contrato" in motivo_analise or "dados" in motivo_analise
            ):
                transbordo_fechamento_pendente = True
            else:
                await TransbordoService.executar_transbordo(
                    db=db,
                    lead=lead,
                    motivo=analise.justificativa,
                    analise=analise
                )
                asyncio.create_task(cls.disparar_auditoria_background(lead_id))
                logger.warning(f"[TRANSBORDO ACIONADO] 🛑 Lead {telefone} em transbordo. IA silenciada.")
                return

        desfecho_mudou_para_fechado = (
            analise.desfecho_sugerido in [models.DesfechoLead.GANHO, models.DesfechoLead.PERDIDO]
            and (desfecho_anterior != analise.desfecho_sugerido or not lead.dossie_comercial)
        )
        if desfecho_mudou_para_fechado:
            asyncio.create_task(cls.disparar_auditoria_background(lead_id))

        nome_ia = str(lead.nome or nome_contato or "Cliente")
        lead_id = getattr(lead, "id")
        pacing_eval = await ConversationPacingService.avaliar_e_incrementar(
            lead_id=lead_id,
            etapa=lead.etapa_funil,
            nome_cliente=nome_ia
        )

        if pacing_eval.deve_encerrar_por_estagnacao:
            lead.desfecho = models.DesfechoLead.PERDIDO
            lead.temperatura = models.TemperaturaLead.FRIO
            lead.motivo_perda = f"Estagnação Conversacional ({pacing_eval.mensagens_na_etapa} msgs em {lead.etapa_funil.value})"
            await db.commit()

            despedida_humana = pacing_eval.mensagem_despedida_humana or OptOutGuard.MENSAGEM_CONFIRMACAO
            await LeadRepository.add_interaction(db, lead_id, models.InteracaoOrigem.IA, despedida_humana)
            await cls.whatsapp_gateway.enviar_mensagem(telefone, despedida_humana, delay_ms=1000)
            await FollowupService.cancelar_followups_pendentes(db, lead_id, models.StatusFollowup.ABORTADO)
            asyncio.create_task(cls.disparar_auditoria_background(lead_id))
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
        if lead.controle in [models.ControleAtendimento.HUMANO_ASSUMIU, models.ControleAtendimento.TRANSBORDO_SOLICITADO] or lead.opt_out:
            logger.warning(
                f"[COLISAO EM VOO EVITADA] 🛑 Disparo da IA cancelado para {telefone}. "
                f"Controle alterado para {lead.controle.value} (Opt-out: {lead.opt_out}) durante o processamento da IA."
            )
            return

        partes_mensagem, _ = await cls.whatsapp_gateway.enviar_mensagem_humanizada(
            telefone=telefone,
            texto_bruto=resposta_ia,
            delay_base_ms=1500
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
            motivo_fechamento = analise.justificativa or "Fechamento Comercial / Assinatura de Contrato"
            await TransbordoService.executar_transbordo(
                db=db,
                lead=lead,
                motivo=motivo_fechamento,
                analise=analise
            )
            asyncio.create_task(cls.disparar_auditoria_background(lead_id))
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
