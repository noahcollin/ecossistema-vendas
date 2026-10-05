import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services.conversation_pacing_service import (
    ConversationPacingService,
    PacingLevel,
    PacingEvaluation,
)
import models


@pytest.mark.asyncio
async def test_pacing_zona_verde_exploracao():
    """Valida que mensagens abaixo do limite proativo mantêm postura exploratória normal."""
    eval_1 = ConversationPacingService.avaliar_contagem(
        contagem=3,
        etapa=models.EtapaFunil.QUALIFICACAO,
        nome_cliente="Carlos"
    )
    assert eval_1.nivel == PacingLevel.EXPLORACAO
    assert not eval_1.deve_encerrar_por_estagnacao
    assert eval_1.diretriz_proatividade is None
    assert eval_1.mensagem_despedida_humana is None


@pytest.mark.asyncio
async def test_pacing_zona_amarela_conducao_ativa():
    """Valida que a partir de 10 mensagens na etapa, o vendedor recebe diretriz de postura ativa."""
    eval_10 = ConversationPacingService.avaliar_contagem(
        contagem=12,
        etapa=models.EtapaFunil.QUALIFICACAO,
        nome_cliente="Dra. Beatriz"
    )
    assert eval_10.nivel == PacingLevel.CONDUCAO_ATIVA
    assert not eval_10.deve_encerrar_por_estagnacao
    assert eval_10.diretriz_proatividade is not None
    assert "POSTURA ATIVA DE VENDAS" in eval_10.diretriz_proatividade
    assert "QUALIFICACAO" in eval_10.diretriz_proatividade


@pytest.mark.asyncio
async def test_pacing_zona_laranja_decisao_final():
    """Valida que a partir de 20 mensagens na etapa, o vendedor faz chamada decisiva de fechamento."""
    eval_22 = ConversationPacingService.avaliar_contagem(
        contagem=22,
        etapa=models.EtapaFunil.NEGOCIACAO,
        nome_cliente="Marcos"
    )
    assert eval_22.nivel == PacingLevel.DECISAO_FINAL
    assert not eval_22.deve_encerrar_por_estagnacao
    assert eval_22.diretriz_proatividade is not None
    assert "CHAMADA DECISIVA DE FECHAMENTO" in eval_22.diretriz_proatividade


@pytest.mark.asyncio
async def test_pacing_zona_vermelha_estagnacao_finops():
    """Valida que ao atingir 30 mensagens na etapa, aciona encerramento gracioso e humanizado (Zero-Touch)."""
    eval_30 = ConversationPacingService.avaliar_contagem(
        contagem=30,
        etapa=models.EtapaFunil.NEGOCIACAO,
        nome_cliente="João Gabriel"
    )
    assert eval_30.nivel == PacingLevel.ESTAGNADO_LIMITE
    assert eval_30.deve_encerrar_por_estagnacao is True
    assert eval_30.mensagem_despedida_humana is not None
    assert "João" in eval_30.mensagem_despedida_humana
    # Garante ausência total de jargões robóticos de SAC/chatbot
    assert "atendente humano" not in eval_30.mensagem_despedida_humana
    assert "transferir" not in eval_30.mensagem_despedida_humana
    assert "portas" in eval_30.mensagem_despedida_humana.lower()


@pytest.mark.asyncio
async def test_pacing_service_redis_incremento_e_reset():
    """Valida o ciclo de contagem atômica e limpeza de chave no Redis."""
    lead_id = 99999
    etapa = models.EtapaFunil.QUALIFICACAO

    with patch("services.conversation_pacing_service.redis_client") as mock_redis:
        mock_redis.incr = AsyncMock(side_effect=[1, 2, 10])
        mock_redis.expire = AsyncMock()
        mock_redis.delete = AsyncMock()

        # Primeiro incremento (deve expirar com TTL)
        r1 = await ConversationPacingService.avaliar_e_incrementar(lead_id, etapa, "Maria")
        assert r1.mensagens_na_etapa == 1
        assert r1.nivel == PacingLevel.EXPLORACAO
        mock_redis.expire.assert_awaited_once()

        # Segundo incremento
        r2 = await ConversationPacingService.avaliar_e_incrementar(lead_id, etapa, "Maria")
        assert r2.mensagens_na_etapa == 2

        # Reset da etapa quando o lead avança no funil
        await ConversationPacingService.resetar_etapa(lead_id)
        mock_redis.delete.assert_awaited_with(f"pacing:etapa:{lead_id}")
