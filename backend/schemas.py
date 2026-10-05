from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Any, Union
from models import (
    EtapaFunil,
    DesfechoLead,
    ControleAtendimento,
    TemperaturaLead,
    TipoEntradaLead,
    StatusFollowup,
)

# ----------------- ESQUEMAS DO LEAD -----------------

class DadosQualificacao(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cidade: Optional[str] = None
    segmento: Optional[str] = None  # ex: clínica, varejo, escola, barbearia, serviços
    solucao_interesse: Optional[str] = None  # ex: AGENTES_AUTONOMOS, CHAT_INTELIGENTTE, DEMAND_AI
    gargalo_principal: Optional[str] = None  # ex: demora no retorno, atendimento 24/7, múltiplos atendentes
    tamanho_equipe: Optional[str] = None  # ex: 1-5, 6-15, 15+
    detalhes: Optional[str] = None
    objecoes_detectadas: list[str] = Field(default_factory=list)
    dados_cadastrais: Optional[str] = None

# Esquema para quando o cliente nos envia dados (não exigimos ID, é automático)
class LeadCreate(BaseModel):
    nome: Optional[str] = None
    telefone: str
    tipo_entrada: Optional[TipoEntradaLead] = TipoEntradaLead.INBOUND
    origem_canal: Optional[str] = "WHATSAPP_DIRETO"
    etapa_funil: Optional[EtapaFunil] = EtapaFunil.NOVO_CONTATO
    desfecho: Optional[DesfechoLead] = DesfechoLead.EM_ANDAMENTO
    valor_estimado: Optional[float] = None

# Esquema completo de retorno com as 4 dimensões desacopladas
class LeadResponse(BaseModel):
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
    model_config = ConfigDict(from_attributes=True)

    id: int
    origem: str
    texto: str
    data: Optional[str] = None
    criado_em: Optional[datetime] = None


# ----------------- ESQUEMA DE SAÍDA ESTRUTURADA DO AGENTE ANALISTA -----------------

class LeadAnalysisOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resumo_perfil: str  # Resumo narrativo conciso do lead (perfil, dores, necessidades)
    etapa_sugerida: EtapaFunil  # Etapa na esteira de vendas (NOVO_CONTATO, QUALIFICACAO, NEGOCIACAO, FECHAMENTO)
    desfecho_sugerido: DesfechoLead  # Saúde da negociação (EM_ANDAMENTO, GANHO, PERDIDO, CONGELADO_CADENCIA)
    transbordo_sugerido: bool  # True se o lead pediu atendente humano, agressividade ou exceção crítica
    temperatura_sugerida: TemperaturaLead  # Nível de urgência/interesse (FRIO, MORNO, QUENTE)
    origem_canal_detectada: Optional[str] = None  # Origem identificada (META_ADS, GOOGLE_SEARCH, SITE_LANDING_PAGE, INDICACAO, etc.)
    motivo_perda: Optional[str] = None  # Termo curto (1 a 3 palavras) se desfecho for PERDIDO
    valor_estimado: Optional[float] = None  # Valor financeiro do deal/orçamento/fatura se mencionado
    tags_sugeridas: list[str] = Field(default_factory=list)  # Tags comportamentais
    opt_out_detectado: bool = False  # True se o cliente pediu remoção/LGPD (pare, não mande mensagem)
    justificativa: str  # Justificativa da decisão analítica
    dados_qualificacao: DadosQualificacao  # Atributos estruturados do nicho


# ----------------- ESQUEMA DE SAÍDA ESTRUTURADA DO AGENTE AUDITOR -----------------

class DossieResultado(BaseModel):
    model_config = ConfigDict(extra="forbid")

    desfecho: DesfechoLead
    motivo_raiz: Optional[str] = None
    concorrente_citado: Optional[str] = None
    diferencial_decisivo: Optional[str] = None

class DossieProximoPasso(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acao_sugerida: str
    quando_retomar: Optional[str] = None
    dica_de_ouro: str

class DossieComercialOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    historia_do_lead: str
    o_que_agradou: list[str] = Field(default_factory=list)
    pontos_de_atrito_e_queixas: list[str] = Field(default_factory=list)
    resultado_final: DossieResultado
    estrategia_utilizada: str
    nota_atendimento_ia: float
    feedback_para_o_negocio: str
    proximo_passo: DossieProximoPasso
    potencial_reativacao: str  # "ALTO", "MEDIO", "BAIXO"
    tipo_entrada: Optional[str] = None
    origem_canal: Optional[str] = None



# ----------------- ESQUEMAS DO MOTOR DE FOLLOW-UP (RF11 & RF12) -----------------

class FollowupAgendadoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    etapa_funil: EtapaFunil
    tentativa: int
    agendado_para: datetime
    status: StatusFollowup
    mensagem_disparada: Optional[str] = None
    criado_em: Optional[datetime] = None
    atualizado_em: Optional[datetime] = None


# ----------------- ESQUEMAS DE TRANSBORDO HUMANO (RF10) -----------------

class TransbordoAssumirRequest(BaseModel):
    atendente: Optional[str] = "Especialista"

class TransbordoDevolverRequest(BaseModel):
    diretriz_ia: Optional[str] = None
    etapa_sugerida: Optional[EtapaFunil] = None
    valor_estimado: Optional[float] = None

class TransbordoSolicitarRequest(BaseModel):
    motivo: str = "Solicitação manual via painel"
    lead_vip: Optional[bool] = False

class MensagemHumanaManualRequest(BaseModel):
    texto: str
    atendente: Optional[str] = "Atendente"

class MensagemHumanaResponse(BaseModel):
    status: str
    interacao_id: int
    origem: str
    texto: str
    data: str

class TransbordoStatusResponse(BaseModel):
    lead_id: int
    nome: Optional[str] = None
    telefone: str
    controle: ControleAtendimento
    etapa_funil: EtapaFunil
    temperatura: TemperaturaLead
    valor_estimado: Optional[float] = None
    tags: list[str] = Field(default_factory=list)
    mensagem: str


# ----------------- ESQUEMAS DA UAZAPI -----------------

class UazapiChat(BaseModel):
    name: Optional[str] = None
    phone: str
    isGroup: Optional[bool] = False

class UazapiMessage(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    messageid: Optional[str] = None
    fromMe: Optional[bool] = False
    isGroup: Optional[bool] = False
    text: Optional[str] = None
    senderName: Optional[str] = None
    messageType: Optional[str] = None
    fileURL: Optional[str] = None
    content: Optional[Any] = None

class UazapiPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    instanceName: Optional[str] = None
    chat: Optional[UazapiChat] = None
    message: Optional[UazapiMessage] = None

