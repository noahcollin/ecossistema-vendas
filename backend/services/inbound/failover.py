"""
Tratador de Falhas de IA e Failover Operacional (Single Responsibility Principle).
Responsável por silenciar a IA com segurança quando há indisponibilidade de LLM
ou cota esgotada, evitando envio de mensagens desconexas ao cliente real.
"""

import asyncio
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from core.logger import logger
from integrations.redis.buffer import redis_client
from repositories.lead_repository import LeadRepository
import models
import schemas


class InboundFailoverService:
    """
    Tratador de Falhas de IA e Failover Operacional.
    Silencia a IA com segurança quando há indisponibilidade ou falha de cota,
    acionando transbordo para a equipe humana.
    """

    MENSAGEM_SISTEMA_FALHA = (
        "[ALERTA OPERACIONAL]: Créditos da OpenAI esgotados ou indisponibilidade da IA. "
        "A IA foi silenciada para preservar a experiência do cliente. Atendimento transferido para a equipe humana."
    )

    @classmethod
    async def lidar_com_falha_geracao(
        cls,
        db: AsyncSession,
        lead: models.Lead,
        telefone: str,
        analise: Optional[schemas.LeadAnalysisOutput] = None
    ) -> None:
        """Executa a rotina de proteção quando a resposta da IA vem vazia ou com erro."""
        from services.handover import TransbordoService

        logger.critical(
            f"[IA SILENCIADA] 🛑 Nenhuma resposta gerada pela IA para {telefone} "
            f"(créditos esgotados ou falha técnica). Silenciando envio e acionando transbordo humano."
        )

        lead = await LeadRepository.recarregar_lead(db, lead.id) or lead
        LeadRepository.sincronizar_tags(lead, adicionar=["REQUER_ATENCAO", "SEM_CREDITO_OPENAI"])
        lead.controle = models.ControleAtendimento.TRANSBORDO_SOLICITADO
        await db.commit()

        # Registra alerta de sistema no histórico do lead
        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.SISTEMA,
            texto=cls.MENSAGEM_SISTEMA_FALHA
        )

        # Notifica a equipe / supervisor
        motivo_alerta = "Créditos da OpenAI esgotados / Falha na IA. Cliente aguarda resposta humana."
        asyncio.create_task(
            TransbordoService.notificar_equipe(
                lead=lead,
                motivo=motivo_alerta,
                analise=analise
            )
        )

        # Registra flag no Redis para o endpoint /health acusar 'degraded'
        try:
            await redis_client.set("alerta_sistema:openai_sem_creditos", "1", ex=86400)
        except Exception as e:
            logger.warning(f"[FAILOVER REDIS] Falha ao registrar alerta no Redis: {e}")
