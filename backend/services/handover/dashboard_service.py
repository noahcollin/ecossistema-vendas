"""
Serviço de Cockpit e Ações de Dashboard do Operador Humano (Clean Architecture).
Isola as operações manuais de painel: assumir lead, devolver para IA,
envio de mensagem direta e listagem de pendências de atendimento.
"""

from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, cast, String
from fastapi import HTTPException

from core.logger import logger
from repositories.lead_repository import LeadRepository
from services.cadence import FollowupService
from integrations.uazapi import client as uazapi_service
from integrations.redis.buffer import redis_client
import models


class DashboardService:
    """
    Camada de serviço especializada para o painel de controle e operações humanas.
    """

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

        # Se o lead foi devolvido para PILOTO_IA e segue em andamento, reativa follow-up
        if lead.desfecho == models.DesfechoLead.EM_ANDAMENTO:
            await FollowupService.agendar_proximo_followup(db, lead)

        logger.info(f"[TRANSBORDO DEVOLVER] 🤖 Lead ID {lead_id} ({lead.telefone}) devolvido para PILOTO_IA com cadência reativada.")
        return lead

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
