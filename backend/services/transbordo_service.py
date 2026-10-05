import asyncio
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, String
from fastapi import HTTPException

from datetime import datetime, timezone
from core.logger import logger
from core.config import settings
from repositories.lead_repository import LeadRepository
from services.followup_service import FollowupService
from integrations.transbordo_notifier import TransbordoNotifier
from integrations.uazapi import client as uazapi_service
from integrations.redis.buffer import redis_client
import models
import schemas


class TransbordoService:
    """
    Camada de serviço de negócio para Transbordo Humano Dinâmico e Handover.
    Orquestra escalonamento, silenciamento da IA, captura de intervenções
    humanas e retomada contextual do Piloto Automático.
    """

    # Delegação para o gateway de notificações
    formatar_mensagem_alerta = TransbordoNotifier.formatar_alerta_supervisor
    notificar_equipe = TransbordoNotifier.notificar_equipe

    @classmethod
    async def executar_transbordo(
        cls,
        db: AsyncSession,
        lead: models.Lead,
        motivo: str,
        analise: Optional[schemas.LeadAnalysisOutput] = None
    ) -> models.Lead:
        """
        Escala o atendimento para transbordo:
        - Altera controle para TRANSBORDO_SOLICITADO;
        - Aplica tags REQUER_ATENCAO e TRANSBORDO;
        - Cancela imediatamente todos os follow-ups programados;
        - Dispara notificações em background sem mensagens robóticas ao cliente.
        """
        lead.controle = models.ControleAtendimento.TRANSBORDO_SOLICITADO
        tags_adicionar = ["REQUER_ATENCAO", "TRANSBORDO"]
        motivo_lower = (motivo or "").lower()
        if "fechamento" in motivo_lower or "contrato" in motivo_lower:
            tags_adicionar.extend(["PRONTO_FECHAMENTO", "AGUARDANDO_CONTRATO"])
        LeadRepository.sincronizar_tags(lead, adicionar=tags_adicionar)

        await FollowupService.cancelar_followups_pendentes(db, lead.id)

        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.SISTEMA,
            texto=f"[TRANSBORDO ACIONADO] 🚨 Atendimento escalado para a equipe humana. Motivo: {motivo}"
        )

        await db.commit()
        await db.refresh(lead)

        # Prepara snapshot desacoplado do ORM para execução segura em segundo plano
        texto_alerta = cls.formatar_mensagem_alerta(lead, motivo, analise)
        dados_lead = {
            "lead_id": lead.id,
            "nome": lead.nome,
            "telefone": lead.telefone,
            "etapa_funil": lead.etapa_funil.value if hasattr(lead.etapa_funil, "value") else str(lead.etapa_funil),
            "temperatura": lead.temperatura.value if hasattr(lead.temperatura, "value") else str(lead.temperatura),
            "valor_estimado": lead.valor_estimado,
            "resumo_perfil": lead.resumo_perfil,
        }
        asyncio.create_task(cls.notificar_equipe(
            lead=None,
            motivo=motivo,
            analise=analise,
            texto_alerta=texto_alerta,
            dados_lead=dados_lead
        ))

        logger.warning(
            f"[TRANSBORDO EXECUTADO] 🚨 Lead {lead.telefone} em TRANSBORDO_SOLICITADO. "
            f"Motivo: {motivo} | IA Silenciada."
        )
        return lead

    @classmethod
    async def solicitar_transbordo_manual(
        cls,
        db: AsyncSession,
        lead_id: int,
        motivo: str = "Solicitação manual via painel"
    ) -> models.Lead:
        """Aciona transbordo humano manual sob demanda para um lead existente."""
        lead = await LeadRepository.get_by_id(db, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead não encontrado.")
        return await cls.executar_transbordo(db, lead, motivo=motivo)

    @staticmethod
    async def assumir_atendimento(
        db: AsyncSession,
        lead_id: int,
        nome_atendente: str = "Especialista"
    ) -> models.Lead:
        """O atendente humano assume a condução direta da conversa pelo painel."""
        lead = await LeadRepository.get_by_id(db, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead não encontrado para assumir atendimento.")

        lead.controle = models.ControleAtendimento.HUMANO_ASSUMIU
        LeadRepository.sincronizar_tags(lead, adicionar=["EM_ATENDIMENTO_HUMANO"], remover=["REQUER_ATENCAO"])

        await FollowupService.cancelar_followups_pendentes(db, lead.id)

        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.SISTEMA,
            texto=f"[ATENDIMENTO ASSUMIDO] 👤 O consultor {nome_atendente} assumiu a condução direta da conversa."
        )

        await db.commit()
        await db.refresh(lead)
        logger.info(f"[TRANSBORDO ASSUMIR] 👤 Lead ID {lead_id} ({lead.telefone}) assumido por {nome_atendente}.")
        return lead

    @staticmethod
    async def devolver_para_ia(
        db: AsyncSession,
        lead_id: int,
        diretriz_ia: Optional[str] = None,
        etapa_sugerida: Optional[models.EtapaFunil] = None,
        valor_estimado: Optional[float] = None
    ) -> models.Lead:
        """O atendente humano conclui sua intervenção e devolve o controle para a IA."""
        lead = await LeadRepository.get_by_id(db, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead não encontrado para devolver à IA.")

        lead.controle = models.ControleAtendimento.PILOTO_IA
        LeadRepository.sincronizar_tags(lead, remover=["REQUER_ATENCAO", "EM_ATENDIMENTO_HUMANO"])

        if etapa_sugerida:
            lead.etapa_funil = etapa_sugerida
        if valor_estimado is not None:
            lead.valor_estimado = valor_estimado

        if diretriz_ia and diretriz_ia.strip():
            texto_diretriz = f"[DIRETRIZ DA EQUIPE PARA A IA]: {diretriz_ia.strip()}"
            await LeadRepository.add_interaction(
                db=db,
                lead_id=lead.id,
                origem=models.InteracaoOrigem.SISTEMA,
                texto=texto_diretriz
            )
            perfil_atual = lead.resumo_perfil or ""
            lead.resumo_perfil = f"{perfil_atual}\n\n[Instrução da Equipe Humana]: {diretriz_ia.strip()}".strip()

        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.SISTEMA,
            texto="[ATENDIMENTO DEVOLVIDO] 🤖 Atendimento devolvido com sucesso para o Piloto Automático de IA."
        )

        await db.commit()
        await db.refresh(lead)

        # Se o lead foi devolvido para PILOTO_IA e segue em andamento (ex: NEGOCIACAO),
        # reativa imediatamente o motor de cadência de follow-up para vigiar a inércia do cliente
        if lead.desfecho == models.DesfechoLead.EM_ANDAMENTO:
            await FollowupService.agendar_proximo_followup(db, lead)

        logger.info(f"[TRANSBORDO DEVOLVER] 🤖 Lead ID {lead_id} ({lead.telefone}) devolvido para PILOTO_IA com cadência reativada.")
        return lead

    @classmethod
    async def verificar_e_executar_retomada_automatica(
        cls,
        db: AsyncSession,
        lead: models.Lead
    ) -> bool:
        """
        Verifica se o atendimento humano entrou em inatividade prolongada (timeout).
        Caso o atendente não envie mensagens por mais de settings.TRANSBORDO_INACTIVITY_TIMEOUT_MINUTES:
        - Reassume o atendimento para PILOTO_IA de forma automática;
        - Registra log de auditoria no histórico de interações;
        - Reativa o motor de cadência e follow-up se o lead estiver em andamento;
        - Retorna True (permitindo que a IA responda imediatamente à nova mensagem do cliente).
        Caso esteja dentro da janela ativa de intervenção humana:
        - Retorna False (mantendo a IA em silêncio para proteger o atendente).
        """
        timeout_minutos = settings.TRANSBORDO_INACTIVITY_TIMEOUT_MINUTES
        if timeout_minutos <= 0:
            return False

        # Busca a última manifestação da equipe humana (ou o momento do transbordo)
        ultima_manifestacao = await LeadRepository.get_latest_interaction_by_origins(
            db=db,
            lead_id=lead.id,
            origens=[models.InteracaoOrigem.HUMANO, models.InteracaoOrigem.SISTEMA]
        )

        agora_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        ref_tempo = None

        if ultima_manifestacao and ultima_manifestacao.criado_em:
            ref_tempo = ultima_manifestacao.criado_em
            if ref_tempo.tzinfo is not None:
                ref_tempo = ref_tempo.astimezone(timezone.utc).replace(tzinfo=None)
        elif lead.criado_em:
            ref_tempo = lead.criado_em
            if ref_tempo.tzinfo is not None:
                ref_tempo = ref_tempo.astimezone(timezone.utc).replace(tzinfo=None)

        if not ref_tempo:
            return False

        delta_segundos = max(0.0, (agora_utc - ref_tempo).total_seconds())
        delta_minutos = delta_segundos / 60.0

        if delta_minutos < timeout_minutos:
            # Ainda dentro da janela de intervenção humana ativa
            return False

        # Timeout atingido! Executa a transição de volta para o PILOTO_IA
        lead.controle = models.ControleAtendimento.PILOTO_IA
        LeadRepository.sincronizar_tags(lead, remover=["REQUER_ATENCAO", "EM_ATENDIMENTO_HUMANO"])

        texto_retomada = (
            f"[AUTO-RETOMADA IA] 🤖 A IA retomou o controle do atendimento após inatividade "
            f"do atendente humano ({int(delta_minutos)} minutos sem novas mensagens da equipe)."
        )
        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.SISTEMA,
            texto=texto_retomada
        )

        perfil_atual = lead.resumo_perfil or ""
        lead.resumo_perfil = f"{perfil_atual}\n\n[Contexto]: Atendimento retomado automaticamente pela IA após inatividade da equipe humana ({int(delta_minutos)}min).".strip()

        # Reativa cadência se estiver em andamento
        if lead.desfecho == models.DesfechoLead.EM_ANDAMENTO:
            await FollowupService.agendar_proximo_followup(db, lead)

        await db.commit()
        await db.refresh(lead)

        logger.info(
            f"[AUTO-RETOMADA IA] 🤖 Lead ID {lead.id} ({lead.telefone}) retomado para PILOTO_IA após "
            f"{delta_minutos:.1f} minutos de inatividade humana (limite: {timeout_minutos} min)."
        )
        return True

    @staticmethod
    async def capturar_mensagem_humana_whatsapp(
        db: AsyncSession,
        lead: models.Lead,
        texto: str,
        sender_name: Optional[str] = None
    ) -> models.Interacao:
        """Captura intervenção direta de um atendente humano pelo celular ou WhatsApp Web (Zero-Click Takeover)."""
        interacao = await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.HUMANO,
            texto=texto
        )

        if lead.controle != models.ControleAtendimento.HUMANO_ASSUMIU:
            lead.controle = models.ControleAtendimento.HUMANO_ASSUMIU
            LeadRepository.sincronizar_tags(lead, adicionar=["EM_ATENDIMENTO_HUMANO"], remover=["REQUER_ATENCAO"])
            await FollowupService.cancelar_followups_pendentes(db, lead.id)

            quem = sender_name or "Atendente"
            await LeadRepository.add_interaction(
                db=db,
                lead_id=lead.id,
                origem=models.InteracaoOrigem.SISTEMA,
                texto=f"[ZERO-CLICK TAKEOVER] 👤 Intervenção humana direta detectada via WhatsApp ({quem})."
            )
            await db.commit()
            await db.refresh(lead)

        logger.info(f"[TRANSBORDO WHATSAPP] 👤 Mensagem humana gravada para {lead.telefone}.")
        return interacao

    @staticmethod
    async def enviar_mensagem_humana_painel(
        db: AsyncSession,
        lead_id: int,
        texto: str,
        atendente: str = "Atendente"
    ) -> models.Interacao:
        """Envia uma mensagem manual do atendente pelo Dashboard e registra na conversa."""
        lead = await LeadRepository.get_by_id(db, lead_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead não encontrado para envio de mensagem.")

        resposta = await uazapi_service.enviar_mensagem(lead.telefone, texto, delay_ms=1000)
        dados = resposta.get("dados") if isinstance(resposta, dict) else None
        msg_id = dados.get("id") or dados.get("messageid") or dados.get("key", {}).get("id") if isinstance(dados, dict) else None

        if msg_id:
            try:
                await redis_client.setex(f"bot_outbound:{msg_id}", 120, "1")
            except Exception:
                pass

        interacao = await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.HUMANO,
            texto=texto
        )

        if lead.controle != models.ControleAtendimento.HUMANO_ASSUMIU:
            lead.controle = models.ControleAtendimento.HUMANO_ASSUMIU
            LeadRepository.sincronizar_tags(lead, adicionar=["EM_ATENDIMENTO_HUMANO"], remover=["REQUER_ATENCAO"])

        await FollowupService.cancelar_followups_pendentes(db, lead.id)
        await db.commit()
        await db.refresh(lead)

        logger.info(f"[MENSAGEM PAINEL] 📤 Mensagem enviada por {atendente} para Lead ID {lead_id}.")
        return interacao

    @staticmethod
    async def listar_pendentes(
        db: AsyncSession,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[models.Lead]:
        """Lista leads aguardando atenção ou em atendimento humano com suporte opcional a paginação."""
        query = (
            select(models.Lead)
            .where(
                cast(models.Lead.controle, String).in_([
                    models.ControleAtendimento.TRANSBORDO_SOLICITADO.value,
                    models.ControleAtendimento.HUMANO_ASSUMIU.value,
                    "TRANSBORDO_SOLICITADO",
                    "HUMANO_ASSUMIU"
                ])
            )
            .order_by(models.Lead.criado_em.desc())
        )
        if limit is not None:
            query = query.limit(limit).offset(offset)
        resultado = await db.execute(query)
        return list(resultado.scalars().all())

    @staticmethod
    async def iniciar_atendimento_humano_outbound(
        db: AsyncSession,
        telefone: str,
        nome_contato: Optional[str],
        texto: str,
        sender_name: Optional[str] = None
    ) -> models.Lead:
        """
        Cadastra um novo lead originado por iniciativa direta de um atendente humano (Outbound Humano):
        - Cria lead com tipo_entrada = OUTBOUND, controle = HUMANO_ASSUMIU e tags = ['OUTBOUND', 'EM_ATENDIMENTO_HUMANO'];
        - Grava a mensagem inicial como InteracaoOrigem.HUMANO;
        - Registra log de auditoria no histórico;
        - Impede a IA de interferir quando o cliente responder.
        """
        lead = await LeadRepository.create(
            db=db,
            telefone=telefone,
            nome=nome_contato if (nome_contato and nome_contato != "Desconhecido") else None,
            tipo_entrada=models.TipoEntradaLead.OUTBOUND,
            origem_canal="WHATSAPP_DIRETO",
            etapa_funil=models.EtapaFunil.NOVO_CONTATO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.HUMANO_ASSUMIU,
            temperatura=models.TemperaturaLead.MORNO,
            tags=["OUTBOUND", "EM_ATENDIMENTO_HUMANO"]
        )

        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.HUMANO,
            texto=texto
        )

        quem = sender_name or "Consultor"
        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.SISTEMA,
            texto=f"[OUTBOUND HUMANO] 👤 Atendimento iniciado diretamente pelo atendente no WhatsApp ({quem})."
        )

        logger.info(
            f"[OUTBOUND HUMANO] 👤 Novo lead criado a partir de mensagem direta do atendente para {telefone}."
        )
        return lead

