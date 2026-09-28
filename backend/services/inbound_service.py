import asyncio
import re
import unicodedata
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
from services.message_consolidation import MessageConsolidator, default_message_consolidator
from integrations.uazapi.gateway import default_uazapi_gateway
from integrations.redis.gateway import default_redis_buffer_gateway
import agents
import models
import schemas


class InboundService:
    """
    Orquestrador de Conversação Inbound (Clean Application Service).
    Coordena o pipeline completo de entrada: debounce, normalização multimídia,
    persistência de lead, travas de segurança, análise cognitiva e resposta do vendedor.
    Suporta Inversão de Dependências (DIP) para testes e gateways desacoplados.
    """

    # Injeção de dependências de infraestrutura (DIP) com defaults canônicos
    whatsapp_gateway: WhatsAppGatewayProtocol = default_uazapi_gateway
    buffer_gateway: CacheBufferProtocol = default_redis_buffer_gateway
    message_consolidator: MessageConsolidator = default_message_consolidator

    # Semáforo Global de Concorrência de IA (FinOps / Proteção contra Rate Limits)
    SEMAFORO_CONCORRENCIA_IA = asyncio.Semaphore(settings.CONCURRENCY_SEMAPHORE_LIMIT)

    @classmethod
    async def processar_debounce(cls, telefone: str, nome_contato: str, timestamp_disparo: float) -> None:
        """
        Ponto de entrada assíncrono acionado pelo Webhook.
        Aguarda a janela de agrupamento (debounce) e processa o lote de mensagens.
        """
        try:
            # 1. Aguarda a janela de digitação do cliente
            await asyncio.sleep(settings.DEBOUNCE_SECONDS)

            # 2. Verifica se houve novas mensagens após esta tarefa
            eh_ultima = await cls.buffer_gateway.verificar_se_e_ultima(telefone, timestamp_disparo)
            if not eh_ultima:
                logger.info(f"[DEBOUNCE] ⏳ Nova mensagem detectada para {telefone}. Descartando lote anterior.")
                return

            logger.info(
                f"[DEBOUNCE] 🚀 Cliente {telefone} parou de digitar por {settings.DEBOUNCE_SECONDS}s. "
                f"Consolidando lote completo..."
            )

            # 3. Desempacota e normaliza todas as mensagens acumuladas no Redis
            texto_consolidado = await cls._consolidar_mensagens_buffer(telefone)
            if not texto_consolidado:
                logger.info(f"[DEBOUNCE] Nenhuma mensagem válida com conteúdo para processar de {telefone}")
                return

            # 4. Executa o pipeline de domínio com sessão de banco de dados
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
        """Orquestra as etapas de negócio para o lead que enviou a mensagem."""
        lead = await cls._obter_ou_criar_lead(db, telefone, nome_contato)

        # 🛡️ TRAVA LGPD: Se o cliente já solicitou opt-out, ignora qualquer envio futuro
        if lead.opt_out:
            logger.info(f"[LGPD OPT-OUT] 🛑 Mensagem de {telefone} ignorada pois o cliente está descadastrado.")
            return

        # 🛡️ FAST-PATH DETERMINÍSTICO LGPD / ANTI-SPAM (Independente de IA)
        if cls._verificar_comando_optout_deterministico(texto_consolidado):
            await cls._executar_optout_deterministico(db, lead, telefone, texto_consolidado)
            return

        # Salva o bloco unificado de mensagens do cliente
        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=texto_consolidado
        )

        # 🛑 CANCELAMENTO REATIVO DE CADÊNCIA (RF12 do PRD): Cliente respondeu!
        await FollowupService.cancelar_followups_pendentes(db, lead.id)

        # 🛡️ TRAVA TRANSBORDO: Se o atendimento está com humano, verifica timeout de inatividade
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

        # Notifica o WhatsApp com status 'digitando...'
        await cls.whatsapp_gateway.enviar_presenca(telefone, presenca="composing", delay_ms=25000)

        # Carrega histórico recente
        historico_recente = await LeadRepository.get_recent_interactions(
            db=db,
            lead_id=lead.id,
            limit=settings.JANELA_HISTORICO_RECENTE
        )

        # 🧠 Execução dos Agentes protegida pelo Semáforo de Concorrência Global
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
        """Executa o Agente Analista (FSM 4D), atualiza dimensões e aciona o Agente Vendedor ('Seu Zé')."""
        # 🧠 AGENTE 1: Analista de Inteligência Comercial (gpt-4o-mini)
        analise = await agents.analisar_lead_e_fsm(
            lead=lead,
            historico_recente=historico_recente,
            nova_mensagem=texto_consolidado
        )

        # 🛑 TRATAMENTO DE OPT-OUT DETECTADO
        if analise.opt_out_detectado:
            lead.opt_out = True
            lead.desfecho = models.DesfechoLead.PERDIDO
            lead.motivo_perda = "Descadastro / Opt-out LGPD"
            await db.commit()

            despedida = "Entendido com certeza. Suas preferências de contato foram atualizadas e não enviaremos mais mensagens por aqui. Agradecemos a atenção e ficamos à disposição caso precise no futuro!"
            await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.IA, despedida)
            await cls.whatsapp_gateway.enviar_mensagem(telefone, despedida, delay_ms=1000)
            logger.info(f"[LGPD OPT-OUT] 🛑 Lead {telefone} descadastrado com sucesso.")
            return

        # Atualiza canal de origem se identificado
        if analise.origem_canal_detectada:
            if not lead.origem_canal or lead.origem_canal == "WHATSAPP_DIRETO":
                lead.origem_canal = analise.origem_canal_detectada

        # Registra desfecho anterior para evitar re-auditorias desnecessárias
        desfecho_anterior = lead.desfecho

        # Atualiza dimensões de vendas e inteligência comercial
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

        await db.commit()

        # 🚨 TRATAMENTO DE TRANSBORDO HUMANO (RF10 do PRD)
        if analise.transbordo_sugerido:
            await TransbordoService.executar_transbordo(
                db=db,
                lead=lead,
                motivo=analise.justificativa,
                analise=analise
            )
            asyncio.create_task(cls.disparar_auditoria_background(lead.id))
            logger.warning(f"[TRANSBORDO ACIONADO] 🛑 Lead {telefone} em transbordo. IA silenciada.")
            return

        # Auditoria executiva apenas na transição de fechamento (GANHO/PERDIDO) ou se ainda não possuir dossiê
        desfecho_mudou_para_fechado = (
            analise.desfecho_sugerido in [models.DesfechoLead.GANHO, models.DesfechoLead.PERDIDO]
            and (desfecho_anterior != analise.desfecho_sugerido or not lead.dossie_comercial)
        )
        if desfecho_mudou_para_fechado:
            asyncio.create_task(cls.disparar_auditoria_background(lead.id))

        # 🤖 AGENTE 2: Vendedor Consultivo 'Seu Zé' (gpt-4o com FinOps)
        nome_ia = lead.nome or nome_contato
        resposta_ia = await agents.gerar_resposta_vendedor(
            nome_cliente_bruto=nome_ia,
            ficha_resumo=lead.resumo_perfil,
            etapa_funil=lead.etapa_funil,
            historico_recente=historico_recente
        )

        # 🛡️ GUARDA PRÉ-DISPARO (ANTI-COLISÃO EM VOO):
        # Enquanto a IA formulava a resposta (latência de LLM), um atendente humano
        # pode ter assumido a conversa no WhatsApp Web ou o lead pode ter solicitado opt-out.
        lead = await LeadRepository.recarregar_lead(db, lead.id) or lead

        if lead.controle in [models.ControleAtendimento.HUMANO_ASSUMIU, models.ControleAtendimento.TRANSBORDO_SOLICITADO] or lead.opt_out:
            logger.warning(
                f"[COLISAO EM VOO EVITADA] 🛑 Disparo da IA cancelado para {telefone}. "
                f"Controle alterado para {lead.controle.value} (Opt-out: {lead.opt_out}) durante o processamento da IA."
            )
            return

        # Dispara a resposta comercial dividida em múltiplos balões com presença humanizada (SRP / DRY)
        partes_mensagem, sucesso_envio = await cls.whatsapp_gateway.enviar_mensagem_humanizada(
            telefone=telefone,
            texto_bruto=resposta_ia,
            delay_base_ms=1500
        )

        # Salva a resposta da IA no histórico (formato limpo legível para o CRM/Dashboard, sem |||)
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

        # 📅 MOTOR DE CADÊNCIA E FOLLOW-UP PROATIVO (RF11 do PRD)
        await FollowupService.agendar_proximo_followup(db, lead)

    @staticmethod
    def dividir_mensagens_whatsapp(texto: str) -> list[str]:
        """Delega para a função utilitária pura centralizada em core.utils (compatibilidade)."""
        from core.utils import dividir_mensagens_whatsapp as _dividir
        return _dividir(texto)

    @staticmethod
    async def disparar_auditoria_background(lead_id: int) -> None:
        """Executa a auditoria em background sem bloquear a resposta no WhatsApp."""
        try:
            async with AsyncSessionLocal() as bg_db:
                await LeadService.gerar_dossie_lead(bg_db, lead_id)
        except Exception as exc:
            logger.error(f"[AUDITOR BACKGROUND ERRO] Falha ao gerar dossiê para Lead ID {lead_id}: {exc}")

    @staticmethod
    def _verificar_comando_optout_deterministico(texto: str) -> bool:
        """
        Detecta comandos determinísticos de descadastro (LGPD / Anti-Spam / Fast-Path).
        Opera de forma 100% autônoma e independente de LLMs para garantir conformidade mesmo em outages.
        """
        if not texto:
            return False

        # Normaliza removendo acentuação e convertendo para maiúsculo
        texto_limpo = unicodedata.normalize("NFKD", texto).encode("ASCII", "ignore").decode("utf-8").upper().strip()

        # Palavras exatas ou comandos curtos isolados
        palavras_comando = {"STOP", "PARE", "SAIR", "CANCELAR", "DESCADASTRAR", "DESCADASTRO"}
        tokens = re.findall(r"\b[A-Z]+\b", texto_limpo)
        if any(token in palavras_comando for token in tokens):
            return True

        # Frases compostas de recusa
        frases_gatilho = [
            "NAO QUERO MAIS",
            "REMOVER MEU NUMERO",
            "TIRAR MEU NUMERO",
            "NAO ME MANDE",
            "NAO ENVIE MAIS",
            "CANCELAR MENSAGENS",
            "PARAR DE MANDAR"
        ]
        return any(frase in texto_limpo for frase in frases_gatilho)

    @classmethod
    async def _executar_optout_deterministico(
        cls,
        db: AsyncSession,
        lead: models.Lead,
        telefone: str,
        texto_recebido: str
    ) -> None:
        """
        Executa o opt-out determinístico sem chamar agentes de IA (Fast-Path).
        Cancela follow-ups, atualiza o status do lead e envia confirmação formal.
        """
        lead.opt_out = True
        lead.desfecho = models.DesfechoLead.PERDIDO
        lead.motivo_perda = "Descadastro / Opt-out LGPD (Comando Determinístico)"
        await db.commit()

        # Salva a mensagem recebida do cliente
        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=texto_recebido
        )

        # Cancela qualquer follow-up pendente
        await FollowupService.cancelar_followups_pendentes(db, lead.id, models.StatusFollowup.ABORTADO)

        despedida = (
            "Entendido com certeza. Suas preferências de contato foram atualizadas "
            "e não enviaremos mais mensagens por aqui. Agradecemos a atenção e ficamos à disposição caso precise no futuro!"
        )
        await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.IA, despedida)
        await cls.whatsapp_gateway.enviar_mensagem(telefone, despedida, delay_ms=1000)
        logger.warning(f"[LGPD OPT-OUT DETERMINÍSTICO] 🛑 Lead {telefone} descadastrado via fast-path (sem dependência de IA).")
