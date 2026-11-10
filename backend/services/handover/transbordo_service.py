"""
Serviço de Domínio para Transbordo Humano Dinâmico e Handover (Clean Architecture).
Utiliza composição explícita em vez de herança acoplada com DashboardService (SOLID / LSP).
"""

from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from core.background import spawn_background_task
from core.logger import logger
from core.config import settings
from repositories.lead_repository import LeadRepository
from services.cadence import FollowupService
from services.handover.dashboard_service import DashboardService
from integrations.transbordo_notifier import TransbordoNotifier
from integrations.send_inteligentte.client import solicitar_handover_send
import models
import schemas


class TransbordoService:
    """
    Orquestra escalonamento, silenciamento da IA, captura de intervenções
    humanas e retomada contextual do Piloto Automático.
    Expõe operações de painel por composição explícita com DashboardService.
    """

    # Composição explícita para o gateway de notificações
    formatar_mensagem_alerta = staticmethod(TransbordoNotifier.formatar_alerta_supervisor)
    notificar_equipe = staticmethod(TransbordoNotifier.notificar_equipe)

    # Composição explícita com DashboardService (substitui herança acoplada mantendo 100% da interface)
    assumir_atendimento = staticmethod(DashboardService.assumir_atendimento)
    devolver_para_ia = staticmethod(DashboardService.devolver_para_ia)
    enviar_mensagem_humana_painel = DashboardService.enviar_mensagem_humana_painel
    listar_pendentes = staticmethod(DashboardService.listar_pendentes)

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
        - Aplica tags REQUER_ATENCAO e TRANSBORDO (e PRONTO_FECHAMENTO quando aplicável);
        - Cancela imediatamente todos os follow-ups programados;
        - Dispara notificações rastreadas em background sem mensagens robóticas ao cliente.
        """
        lead.controle = models.ControleAtendimento.TRANSBORDO_SOLICITADO
        tags_adicionar = ["REQUER_ATENCAO", "TRANSBORDO"]
        motivo_lower = (motivo or "").lower()
        eh_fechamento = bool(
            (analise and getattr(analise, "pronto_fechamento", False))
            or "fechamento" in motivo_lower
            or "contrato" in motivo_lower
        )
        if eh_fechamento:
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
        spawn_background_task(
            cls.notificar_equipe(
                lead=None,
                motivo=motivo,
                analise=analise,
                texto_alerta=texto_alerta,
                dados_lead=dados_lead
            ),
            name=f"notificar_transbordo_{lead.id}",
        )

        if settings.SEND_API_KEY and lead.telefone:
            spawn_background_task(
                solicitar_handover_send(telefone=lead.telefone, reason=motivo),
                name=f"send_handover_{lead.id}",
            )

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

    @classmethod
    async def verificar_e_executar_retomada_automatica(
        cls,
        db: AsyncSession,
        lead: models.Lead
    ) -> bool:
        """
        Verifica se o atendimento humano entrou em inatividade prolongada (timeout).
        Retorna True se reassumiu para PILOTO_IA ou False se ainda dentro da janela humana.
        """
        timeout_minutos = settings.TRANSBORDO_INACTIVITY_TIMEOUT_MINUTES
        if timeout_minutos <= 0:
            return False

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
            return False

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
        lead.resumo_perfil = (
            f"{perfil_atual}\n\n[Contexto]: Atendimento retomado automaticamente pela IA "
            f"após inatividade da equipe humana ({int(delta_minutos)}min)."
        ).strip()

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
    async def iniciar_atendimento_humano_outbound(
        db: AsyncSession,
        telefone: str,
        nome_contato: Optional[str],
        texto: str,
        sender_name: Optional[str] = None
    ) -> models.Lead:
        """Cadastra um novo lead originado por iniciativa direta de um atendente humano (Outbound Humano)."""
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
