from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update
import models

class FollowupRepository:
    """
    Camada de persistência para a entidade FollowupAgendado.
    Responsável pelo agendamento, cancelamento reativo e consulta de tarefas de cadência.
    """

    @staticmethod
    async def criar(
        db: AsyncSession,
        lead_id: int,
        etapa_funil: models.EtapaFunil,
        tentativa: int,
        agendado_para: datetime
    ) -> models.FollowupAgendado:
        """Cria um novo agendamento de follow-up."""
        novo = models.FollowupAgendado(
            lead_id=lead_id,
            etapa_funil=etapa_funil,
            tentativa=tentativa,
            agendado_para=agendado_para,
            status=models.StatusFollowup.PENDENTE
        )
        db.add(novo)
        await db.commit()
        await db.refresh(novo)
        return novo

    @staticmethod
    async def cancelar_pendentes_por_lead(
        db: AsyncSession,
        lead_id: int,
        motivo: models.StatusFollowup = models.StatusFollowup.CANCELADO_POR_RESPOSTA
    ) -> int:
        """
        Cancela de forma atômica todos os follow-ups pendentes para um lead específico.
        Implementa o requisito RF12 do PRD (Interrupção Imediata por Interação).
        """
        stmt = (
            update(models.FollowupAgendado)
            .where(
                models.FollowupAgendado.lead_id == lead_id,
                models.FollowupAgendado.status == models.StatusFollowup.PENDENTE
            )
            .values(status=motivo)
        )
        resultado = await db.execute(stmt)
        await db.commit()
        return resultado.rowcount

    @staticmethod
    async def obter_vencidos_pendentes(
        db: AsyncSession,
        limite: int = 50,
        data_referencia: Optional[datetime] = None
    ) -> List[models.FollowupAgendado]:
        """
        Recupera follow-ups com status PENDENTE cuja data agendada já foi atingida.
        """
        agora = data_referencia or datetime.now(timezone.utc).replace(tzinfo=None)
        query = (
            select(models.FollowupAgendado)
            .where(
                models.FollowupAgendado.status == models.StatusFollowup.PENDENTE,
                models.FollowupAgendado.agendado_para <= agora
            )
            .order_by(models.FollowupAgendado.agendado_para.asc())
            .limit(limite)
        )
        resultado = await db.execute(query)
        return list(resultado.scalars().all())

    @staticmethod
    async def obter_ultima_tentativa(
        db: AsyncSession,
        lead_id: int
    ) -> Optional[models.FollowupAgendado]:
        """Obtém o registro mais recente de follow-up de um lead."""
        query = (
            select(models.FollowupAgendado)
            .where(models.FollowupAgendado.lead_id == lead_id)
            .order_by(models.FollowupAgendado.id.desc())
            .limit(1)
        )
        resultado = await db.execute(query)
        return resultado.scalars().first()

    @staticmethod
    async def obter_pendente_por_lead(
        db: AsyncSession,
        lead_id: int
    ) -> Optional[models.FollowupAgendado]:
        """Verifica se existe algum follow-up ativo pendente para o lead."""
        query = (
            select(models.FollowupAgendado)
            .where(
                models.FollowupAgendado.lead_id == lead_id,
                models.FollowupAgendado.status == models.StatusFollowup.PENDENTE
            )
            .limit(1)
        )
        resultado = await db.execute(query)
        return resultado.scalars().first()

    @staticmethod
    async def listar_por_lead(
        db: AsyncSession,
        lead_id: int
    ) -> List[models.FollowupAgendado]:
        """Recupera todos os agendamentos de follow-up de um lead ordenados cronologicamente."""
        query = (
            select(models.FollowupAgendado)
            .where(models.FollowupAgendado.lead_id == lead_id)
            .order_by(models.FollowupAgendado.id.desc())
        )
        resultado = await db.execute(query)
        return list(resultado.scalars().all())

    @staticmethod
    async def marcar_como_disparado(
        db: AsyncSession,
        followup: models.FollowupAgendado,
        mensagem_texto: str
    ) -> models.FollowupAgendado:
        """Marca o follow-up como disparado com sucesso, registrando o texto enviado."""
        followup.status = models.StatusFollowup.DISPARADO
        followup.mensagem_disparada = mensagem_texto
        await db.commit()
        await db.refresh(followup)
        return followup

    @staticmethod
    async def atualizar_status(
        db: AsyncSession,
        followup: models.FollowupAgendado,
        novo_status: models.StatusFollowup
    ) -> models.FollowupAgendado:
        """Atualiza o status de um registro de follow-up."""
        followup.status = novo_status
        await db.commit()
        await db.refresh(followup)
        return followup
