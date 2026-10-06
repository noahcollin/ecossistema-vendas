"""
Entidade Interacao e tabela 'interacoes' para registro auditável do histórico de conversas.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Index
from sqlalchemy.orm import relationship

from core.database import Base
from .enums import InteracaoOrigem


class Interacao(Base):
    """
    Registro individual de mensagem trocada (Cliente, IA, Humano ou Sistema).
    """
    __tablename__ = "interacoes"
    __table_args__ = (
        Index("ix_interacoes_lead_criado", "lead_id", "criado_em"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False)
    origem = Column(Enum(InteracaoOrigem), nullable=False)
    texto = Column(String, nullable=False)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    # Ligação de volta para a ficha do Lead
    lead = relationship("Lead", back_populates="interacoes")
