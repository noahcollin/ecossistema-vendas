"""
Entidade Lead e tabela 'leads' com suporte às 4 dimensões desacopladas de vendas.
"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from core.database import Base
from .enums import EtapaFunil, DesfechoLead, ControleAtendimento, TemperaturaLead, TipoEntradaLead


class Lead(Base):
    """
    Entidade de persistência do Lead no ecossistema comercial.
    Armazena histórico, tags comportamentais, inteligência analítica e as 4 dimensões de vendas.
    """
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, index=True, nullable=True)
    telefone = Column(String, unique=True, index=True, nullable=False)
    
    # Aquisição e Origem Comercial
    tipo_entrada = Column(Enum(TipoEntradaLead), default=TipoEntradaLead.INBOUND, index=True)
    origem_canal = Column(String, default="WHATSAPP_DIRETO", index=True)

    # As 4 Dimensões de Negócio
    etapa_funil = Column(Enum(EtapaFunil), default=EtapaFunil.NOVO_CONTATO, index=True)
    desfecho = Column(Enum(DesfechoLead), default=DesfechoLead.EM_ANDAMENTO, index=True)
    controle = Column(Enum(ControleAtendimento), default=ControleAtendimento.PILOTO_IA, index=True)
    temperatura = Column(Enum(TemperaturaLead), default=TemperaturaLead.FRIO, index=True)
    
    # Inteligência e Métricas Analíticas
    motivo_perda = Column(String, nullable=True, index=True)  # ex: Preço, Concorrência, Sem Perfil
    valor_estimado = Column(Float, nullable=True)  # Valor do deal/orçamento/ticket agnóstico
    tags = Column(JSONB().with_variant(JSON, "sqlite"), default=list)  # Tags comportamentais
    opt_out = Column(Boolean, default=False, index=True)  # Trava LGPD / descadastro
    
    # Memória do Lead e Atributos Dinâmicos do Nicho
    resumo_perfil = Column(String, nullable=True)  # Ficha narrativa do lead
    dados_qualificacao = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)  # Dados específicos do nicho em JSON
    dossie_comercial = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)  # Auditoria executiva completa do lead
    
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    # Relacionamentos com exclusão em cascata
    interacoes = relationship("Interacao", back_populates="lead", cascade="all, delete-orphan")
    followups = relationship("FollowupAgendado", back_populates="lead", cascade="all, delete-orphan")
