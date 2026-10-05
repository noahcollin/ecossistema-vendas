"""
Testes Unitários de Inversão de Dependências (DIP) e Serviços de Mensageria.
"""

import pytest
from services.message_consolidation import MessageConsolidator
from services.inbound_service import InboundService
from tests.conftest import MockCacheBufferGateway, MockWhatsAppGateway


@pytest.mark.asyncio
async def test_message_consolidator_multi_messages():
    """Valida a consolidação de múltiplas mensagens empilhadas no buffer."""
    mock_buffer = MockCacheBufferGateway()
    tel = "+5583999990001"
    
    await mock_buffer.adicionar_mensagem(tel, '{"text": "Primeira mensagem"}')
    await mock_buffer.adicionar_mensagem(tel, '{"text": "Segunda mensagem"}')

    consolidator = MessageConsolidator(buffer_gateway=mock_buffer)
    texto = await consolidator.consolidar_buffer(tel)

    assert texto == "Primeira mensagem\nSegunda mensagem"


@pytest.mark.asyncio
async def test_message_consolidator_truncation_guard():
    """Valida a proteção contra payload gigantesco (estouro de contexto de LLM)."""
    mock_buffer = MockCacheBufferGateway()
    tel = "+5583999990002"
    
    # Adiciona texto que excede o limite configurado
    texto_longo = "A" * 500
    await mock_buffer.adicionar_mensagem(tel, texto_longo)

    consolidator = MessageConsolidator(buffer_gateway=mock_buffer)
    resultado = await consolidator.consolidar_buffer(tel, max_caracteres=100)

    assert len(resultado) > 100
    assert "[... texto truncado por exceder o limite de segurança ...]" in resultado


def test_inbound_service_deterministic_optout_detection():
    """Valida a detecção determinística de comandos de opt-out (LGPD Fast-Path)."""
    assert InboundService._verificar_comando_optout_deterministico("SAIR") is True
    assert InboundService._verificar_comando_optout_deterministico("pare de me mandar mensagens") is True
    assert InboundService._verificar_comando_optout_deterministico("NÃO QUERO MAIS") is True
    assert InboundService._verificar_comando_optout_deterministico("Favor remover meu numero") is True
    assert InboundService._verificar_comando_optout_deterministico("Quero fazer um orçamento") is False
    assert InboundService._verificar_comando_optout_deterministico("") is False


@pytest.mark.asyncio
async def test_closer_agent_silence_on_quota_exhaustion(monkeypatch):
    """Garante que o Closer Agent retorne None (e NUNCA envie mensagem ao cliente) quando a cota acabar."""
    import agents.sales_closer_agent as closer_module
    from agents.sales_closer_agent import gerar_resposta_vendedor, gerar_mensagem_followup

    async def mock_completions_error(*args, **kwargs):
        raise Exception("Error code: 429 - {'error': {'message': 'You exceeded your current quota', 'code': 'insufficient_quota'}}")

    monkeypatch.setattr(closer_module.openai_client.chat.completions, "create", mock_completions_error)

    # 1. Teste no vendedor consultivo
    resp_vendedor = await gerar_resposta_vendedor(
        nome_cliente_bruto="João",
        ficha_resumo="Interesse em energia solar",
        etapa_funil=None,
        historico_recente=[]
    )
    assert resp_vendedor is None

    # 2. Teste no follow-up
    resp_followup = await gerar_mensagem_followup(
        nome_cliente_bruto="João",
        ficha_resumo="Interesse em energia solar",
        etapa_funil=None,
        tentativa=1,
        historico_recente=[]
    )
    assert resp_followup is None


@pytest.mark.asyncio
async def test_inbound_service_silences_whatsapp_on_ai_failure(monkeypatch):
    """
    Garante que se o Closer Agent retornar None, o InboundService:
    1. NÃO envia nenhuma mensagem via WhatsApp (silêncio total para o cliente).
    2. Coloca o lead em TRANSBORDO_SOLICITADO.
    3. Adiciona a tag SEM_CREDITO_OPENAI.
    """
    from unittest.mock import AsyncMock
    import schemas
    import models
    from repositories.lead_repository import LeadRepository

    mock_gw = MockWhatsAppGateway()
    InboundService.whatsapp_gateway = mock_gw

    # Mock do Analista retornando análise padrão sem transbordo inicial
    analise_mock = schemas.LeadAnalysisOutput(
        resumo_perfil="Perfil teste",
        etapa_sugerida=models.EtapaFunil.NOVO_CONTATO,
        desfecho_sugerido=models.DesfechoLead.EM_ANDAMENTO,
        transbordo_sugerido=False,
        temperatura_sugerida=models.TemperaturaLead.MORNO,
        justificativa="Fluxo normal",
        dados_qualificacao=schemas.DadosQualificacao(),
    )
    monkeypatch.setattr("agents.analisar_lead_e_fsm", AsyncMock(return_value=analise_mock))

    # Mock do Closer Agent retornando None (cota esgotada)
    monkeypatch.setattr("agents.gerar_resposta_vendedor", AsyncMock(return_value=None))

    # Mock do Lead e Session
    lead = models.Lead(id=999, telefone="+5583999999999", controle=models.ControleAtendimento.PILOTO_IA, tags=[])

    mock_db = AsyncMock()
    monkeypatch.setattr(LeadRepository, "recarregar_lead", AsyncMock(return_value=lead))
    monkeypatch.setattr(LeadRepository, "add_interaction", AsyncMock())
    monkeypatch.setattr("services.transbordo_service.TransbordoService.notificar_equipe", AsyncMock())
    monkeypatch.setattr("integrations.redis.buffer.redis_client.set", AsyncMock())

    await InboundService._processar_cognicao_e_resposta(
        db=mock_db,
        lead=lead,
        telefone="+5583999999999",
        nome_contato="Cliente Teste",
        texto_consolidado="Olá",
        historico_recente=[]
    )

    # 1. WhatsApp DEVE estar 100% silencioso (zero mensagens enviadas)
    assert len(mock_gw.mensagens_enviadas) == 0

    # 2. Lead foi movido para transbordo solicitado
    assert lead.controle == models.ControleAtendimento.TRANSBORDO_SOLICITADO

    # 3. Tags de alerta operacional foram aplicadas
    assert "SEM_CREDITO_OPENAI" in lead.tags
    assert "REQUER_ATENCAO" in lead.tags
