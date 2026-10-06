"""
Esquemas Pydantic v2 para Lead, Qualificação de Nicho e Histórico de Interações.
"""

from datetime import datetime
from typing import Optional, Any, Union
from pydantic import BaseModel, ConfigDict, Field
from models import (
    EtapaFunil,
    DesfechoLead,
    ControleAtendimento,
    TemperaturaLead,
    TipoEntradaLead,
)


class DadosQualificacao(BaseModel):
    """Atributos de diagnóstico do cliente levantados durante a conversa."""
    model_config = ConfigDict(extra="forbid")

    cidade: Optional[str] = None
    segmento: Optional[str] = None  # ex: clínica, varejo, escola, barbearia, serviços
    solucao_interesse: Optional[str] = None  # ex: AGENTES_AUTONOMOS, CHAT_INTELIGENTTE, DEMAND_AI
    gargalo_principal: Optional[str] = None  # ex: demora no retorno, atendimento 24/7, múltiplos atendentes
    tamanho_equipe: Optional[str] = None  # ex: 1-5, 6-15, 15+
    detalhes: Optional[str] = None
    objecoes_detectadas: list[str] = Field(default_factory=list)
    dados_cadastrais: Optional[str] = None


class LeadCreate(BaseModel):
    """Payload para criação ou entrada inicial de lead no sistema."""
    nome: Optional[str] = None
    telefone: str
    tipo_entrada: Optional[TipoEntradaLead] = TipoEntradaLead.INBOUND
    origem_canal: Optional[str] = "WHATSAPP_DIRETO"
    etapa_funil: Optional[EtapaFunil] = EtapaFunil.NOVO_CONTATO
    desfecho: Optional[DesfechoLead] = DesfechoLead.EM_ANDAMENTO
    valor_estimado: Optional[float] = None


class LeadResponse(BaseModel):
    """Esquema de serialização completo do Lead com as 4 dimensões desacopladas."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: Optional[str] = None
    telefone: str
    
    # Aquisição Comercial
    tipo_entrada: TipoEntradaLead = TipoEntradaLead.INBOUND
    origem_canal: Optional[str] = "WHATSAPP_DIRETO"

    # 4 Dimensões de Negócio
    etapa_funil: EtapaFunil = EtapaFunil.NOVO_CONTATO
    desfecho: DesfechoLead = DesfechoLead.EM_ANDAMENTO
    controle: ControleAtendimento = ControleAtendimento.PILOTO_IA
    temperatura: TemperaturaLead = TemperaturaLead.FRIO
    
    # Inteligência Analítica para o Dashboard
    motivo_perda: Optional[str] = None
    valor_estimado: Optional[float] = None
    tags: list[str] = Field(default_factory=list)
    opt_out: bool = False
    
    # Memória de Longo Prazo
    resumo_perfil: Optional[str] = None
    dados_qualificacao: Optional[Union[DadosQualificacao, dict[str, Any]]] = None
    dossie_comercial: Optional[Union[dict[str, Any], Any]] = None
    criado_em: Optional[datetime] = None


class InteracaoResponse(BaseModel):
    """Serialização de uma mensagem no histórico de conversa."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    origem: str
    texto: str
    data: Optional[str] = None
    criado_em: Optional[datetime] = None
