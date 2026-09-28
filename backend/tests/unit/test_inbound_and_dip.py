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
