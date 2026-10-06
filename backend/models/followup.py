"""
Entidade FollowupAgendado para persistência do Motor de Cadência Temporal.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Index
from sqlalchemy.orm import relationship

from core.database import Base
from .enums import EtapaFunil, StatusFollowup


class FollowupAgendado(Base):
    """
    Entidade de persistência do Motor de Cadência Temporal (RF11 & RF12 do PRD).
    Rastreia agendamentos de resgate, tentativas (1 a 3), janelas de horário e status de cancelamento reativo.
    """
    __tablename__ = "followups_agendados"
    __table_args__ = (
        Index("ix_followup_status_agendado", "status", "agendado_para"),
    )

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    etapa_funil = Column(Enum(EtapaFunil), nullable=False)
    tentativa = Column(Integer, default=1, nullable=False)
    agendado_para = Column(DateTime, nullable=False, index=True)
    status = Column(Enum(StatusFollowup), default=StatusFollowup.PENDENTE, index=True)
    mensagem_disparada = Column(String, nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    atualizado_em = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )

    lead = relationship("Lead", back_populates="followups")
