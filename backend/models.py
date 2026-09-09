from sqlalchemy import Column, Integer, String, DateTime, Enum
from datetime import datetime, timezone
import enum
from database import Base

# Definindo as fases do Funil de Vendas baseadas na Máquina de Estados do PDF
class LeadStatus(str, enum.Enum):
    NOVO = "NOVO_LEAD"
    QUALIFICACAO = "EM_QUALIFICACAO"
    APRESENTACAO = "APRESENTACAO_VALOR"
    OBJECAO = "TRATAMENTO_OBJECAO"
    FECHAMENTO = "FECHAMENTO"
    CONTRATO = "DISPARO_CONTRATO"
    GANHO = "GANHO"
    PERDIDO = "PERDIDO"
    TRANSBORDO = "TRANSBORDO_HUMANO"

# Criando a tabela 'leads'
class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True, nullable=True)
    telefone = Column(String, unique=True, index=True, nullable=False)
    status = Column(Enum(LeadStatus), default=LeadStatus.NOVO)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
