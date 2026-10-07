"""
Entidade ORM para Configurações Operacionais Dinâmicas do Ecossistema.
Permite persistência das regras de negócio (produtos, preços, cadência, horários)
sem necessidade de reinicialização de containers ou alteração de código.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, JSON
from core.database import Base


class ConfiguracaoOperacional(Base):
    """
    Tabela singleton (chave única ou versão) para armazenamento persistente
    dos parâmetros de operação comercial e regras de negócio.
    """
    __tablename__ = "configuracoes_operacionais"

    id = Column(Integer, primary_key=True, index=True)
    chave = Column(String(50), unique=True, nullable=False, default="geral", index=True)
    
    # Payload JSON contendo produtos, cadência, horários e anti-ban
    dados = Column(JSON, nullable=False, default=dict)
    
    atualizado_em = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def __repr__(self) -> str:
        return f"<ConfiguracaoOperacional chave='{self.chave}' atualizado_em='{self.atualizado_em}'>"
