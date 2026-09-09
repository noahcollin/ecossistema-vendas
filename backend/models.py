from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
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
    
    # O "grampo" que liga o Lead aos seus post-its (Interações)
    interacoes = relationship("Interacao", back_populates="lead")

# Definindo quem enviou a mensagem
class InteracaoOrigem(str, enum.Enum):
    CLIENTE = "cliente"
    IA = "ia"
    SISTEMA = "sistema"

# Criando a tabela de post-its (histórico de mensagens)
class Interacao(Base):
    __tablename__ = "interacoes"
    
    id = Column(Integer, primary_key=True, index=True)
    # A Chave Estrangeira: OBRIGA a ter o ID de um lead válido na tabela "leads"
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    origem = Column(Enum(InteracaoOrigem), nullable=False)
    texto = Column(String, nullable=False)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    # Ligação de volta para a ficha do Lead
    lead = relationship("Lead", back_populates="interacoes")
