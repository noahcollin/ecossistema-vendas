from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Enum, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
from core.database import Base

# ----------------- AS 4 DIMENSÕES DE VENDAS DO LEAD -----------------

# Dimensão 1: Jornada sequencial do cliente no funil
class EtapaFunil(str, enum.Enum):
    NOVO_CONTATO = "NOVO_CONTATO"
    QUALIFICACAO = "QUALIFICACAO"
    NEGOCIACAO = "NEGOCIACAO"
    FECHAMENTO = "FECHAMENTO"

# Dimensão 2: Saúde e desfecho da negociação
class DesfechoLead(str, enum.Enum):
    EM_ANDAMENTO = "EM_ANDAMENTO"
    GANHO = "GANHO"
    PERDIDO = "PERDIDO"
    CONGELADO_CADENCIA = "CONGELADO_CADENCIA"

# Dimensão 3: Quem tem o controle da conversa
class ControleAtendimento(str, enum.Enum):
    PILOTO_IA = "PILOTO_IA"
    TRANSBORDO_SOLICITADO = "TRANSBORDO_SOLICITADO"
    HUMANO_ASSUMIU = "HUMANO_ASSUMIU"

# Dimensão 4a: Temperatura do lead (Score de interesse/urgência)
class TemperaturaLead(str, enum.Enum):
    FRIO = "FRIO"
    MORNO = "MORNO"
    QUENTE = "QUENTE"

# Estratégia de Captação do Lead (Inbound vs Outbound)
class TipoEntradaLead(str, enum.Enum):
    INBOUND = "INBOUND"     # Cliente tomou a iniciativa (anúncio, site, indicação, etc.)
    OUTBOUND = "OUTBOUND"   # Empresa tomou a iniciativa (prospecção ativa, lista fria, eventos)

# Enum legado mantido para compatibilidade temporária
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
    
    # Campo legado mantido para retrocompatibilidade temporária
    status = Column(Enum(LeadStatus), default=LeadStatus.NOVO, nullable=True)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    # O "grampo" que liga o Lead aos seus post-its (Interações com exclusão em cascata)
    interacoes = relationship("Interacao", back_populates="lead", cascade="all, delete-orphan")
    followups = relationship("FollowupAgendado", back_populates="lead", cascade="all, delete-orphan")


# Definindo quem enviou a mensagem
class InteracaoOrigem(str, enum.Enum):
    CLIENTE = "cliente"
    IA = "ia"
    HUMANO = "humano"
    SISTEMA = "sistema"

# Criando a tabela de post-its (histórico de mensagens)
class Interacao(Base):
    __tablename__ = "interacoes"
    __table_args__ = (
        Index("ix_interacoes_lead_criado", "lead_id", "criado_em"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    # A Chave Estrangeira: OBRIGA a ter o ID de um lead válido na tabela "leads"
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False)
    origem = Column(Enum(InteracaoOrigem), nullable=False)
    texto = Column(String, nullable=False)
    criado_em = Column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    
    # Ligação de volta para a ficha do Lead
    lead = relationship("Lead", back_populates="interacoes")


# ----------------- MOTOR DE CADÊNCIA E FOLLOW-UP (RF11 & RF12) -----------------

class StatusFollowup(str, enum.Enum):
    PENDENTE = "PENDENTE"
    DISPARADO = "DISPARADO"
    CANCELADO_POR_RESPOSTA = "CANCELADO_POR_RESPOSTA"
    EXPIRADO = "EXPIRADO"
    ABORTADO = "ABORTADO"

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
