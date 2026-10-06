"""
Enums e Tipos das 4 Dimensões de Negócio e Ciclo de Vida do Lead.
"""

import enum


class EtapaFunil(str, enum.Enum):
    """Dimensão 1: Jornada sequencial do cliente no funil."""
    NOVO_CONTATO = "NOVO_CONTATO"
    QUALIFICACAO = "QUALIFICACAO"
    NEGOCIACAO = "NEGOCIACAO"
    FECHAMENTO = "FECHAMENTO"


class DesfechoLead(str, enum.Enum):
    """Dimensão 2: Saúde e desfecho da negociação."""
    EM_ANDAMENTO = "EM_ANDAMENTO"
    GANHO = "GANHO"
    PERDIDO = "PERDIDO"
    CONGELADO_CADENCIA = "CONGELADO_CADENCIA"


class ControleAtendimento(str, enum.Enum):
    """Dimensão 3: Quem tem o controle da conversa."""
    PILOTO_IA = "PILOTO_IA"
    TRANSBORDO_SOLICITADO = "TRANSBORDO_SOLICITADO"
    HUMANO_ASSUMIU = "HUMANO_ASSUMIU"


class TemperaturaLead(str, enum.Enum):
    """Dimensão 4: Score de interesse/urgência do lead."""
    FRIO = "FRIO"
    MORNO = "MORNO"
    QUENTE = "QUENTE"


class TipoEntradaLead(str, enum.Enum):
    """Estratégia de Captação do Lead (Inbound vs Outbound)."""
    INBOUND = "INBOUND"     # Cliente tomou a iniciativa (anúncio, site, indicação, etc.)
    OUTBOUND = "OUTBOUND"   # Empresa tomou a iniciativa (prospecção ativa, lista fria, eventos)


class InteracaoOrigem(str, enum.Enum):
    """Origem do remetente da mensagem gravada na conversa."""
    CLIENTE = "cliente"
    IA = "ia"
    HUMANO = "humano"
    SISTEMA = "sistema"


class StatusFollowup(str, enum.Enum):
    """Status de persistência do Motor de Cadência Temporal."""
    PENDENTE = "PENDENTE"
    DISPARADO = "DISPARADO"
    CANCELADO_POR_RESPOSTA = "CANCELADO_POR_RESPOSTA"
    EXPIRADO = "EXPIRADO"
    ABORTADO = "ABORTADO"
