import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from services.inbound_service import InboundService
from services.conversation_pacing_service import ConversationPacingService, PacingEvaluation, PacingLevel
from repositories.lead_repository import LeadRepository
import models
import schemas


@pytest.mark.asyncio
async def test_inbound_pacing_conducao_ativa_injects_closer_directive(db_session: AsyncSession):
    """
    Testa se ao atingir a Zona Amarela (10+ mensagens na etapa),
    o InboundService repassa a diretriz de postura ativa de vendas para o Closer Agent.
    """
    telefone = "+5583999990101"
    lead = await LeadRepository.get_by_phone(db_session, telefone)
    if not lead:
        lead = await LeadRepository.create(db_session, telefone=telefone, nome="Roberta")
    lead.etapa_funil = models.EtapaFunil.QUALIFICACAO
    lead.desfecho = models.DesfechoLead.EM_ANDAMENTO
    await db_session.commit()

    analise_mock = schemas.LeadAnalysisOutput(
        resumo_perfil="Roberta, clínica estética.",
        etapa_sugerida=models.EtapaFunil.QUALIFICACAO,
        desfecho_sugerido=models.DesfechoLead.EM_ANDAMENTO,
        transbordo_sugerido=False,
        temperatura_sugerida=models.TemperaturaLead.MORNO,
        justificativa="Em diagnóstico",
        dados_qualificacao=schemas.DadosQualificacao(segmento="Clínica")
    )

    with patch("agents.analisar_lead_e_fsm", new_callable=AsyncMock) as mock_analista, \
         patch("agents.gerar_resposta_vendedor", new_callable=AsyncMock) as mock_closer, \
         patch("services.conversation_pacing_service.redis_client.incr", new_callable=AsyncMock) as mock_incr, \
         patch("services.conversation_pacing_service.redis_client.expire", new_callable=AsyncMock), \
         patch.object(InboundService.whatsapp_gateway, "enviar_mensagem_humanizada", new_callable=AsyncMock) as mock_send:

        mock_analista.return_value = analise_mock
        mock_incr.return_value = 12  # 12 mensagens na etapa (Zona Amarela)
        mock_closer.return_value = "Entendi perfeitamente, Roberta! O que você acha de vermos uma demonstração prática?"
        mock_send.return_value = (["Entendi perfeitamente, Roberta! O que você acha de vermos uma demonstração prática?"], True)

        await InboundService._processar_cognicao_e_resposta(
            db=db_session,
            lead=lead,
            telefone=telefone,
            nome_contato="Roberta",
            texto_consolidado="Quanto custa para 3 atendentes?",
            historico_recente=[]
        )

        # Valida que o closer agent foi chamado COM a diretriz de postura ativa
        mock_closer.assert_awaited_once()
        _, kwargs = mock_closer.call_args
        diretriz = kwargs.get("diretriz_proatividade")
        assert diretriz is not None
        assert "POSTURA ATIVA DE VENDAS" in diretriz


@pytest.mark.asyncio
async def test_inbound_pacing_trava_finops_desqualificacao_zero_touch(db_session: AsyncSession):
    """
    Testa se ao atingir 30 mensagens na etapa, o sistema realiza a desqualificação
    100% autônoma e humanizada, marcando PERDIDO, despedindo sem jargões de robô,
    sem disparar transbordo para a equipe humana.
    """
    telefone = "+5583999990102"
    lead = await LeadRepository.get_by_phone(db_session, telefone)
    if not lead:
        lead = await LeadRepository.create(db_session, telefone=telefone, nome="Fernando")
    lead.etapa_funil = models.EtapaFunil.QUALIFICACAO
    lead.desfecho = models.DesfechoLead.EM_ANDAMENTO
    await db_session.commit()

    analise_mock = schemas.LeadAnalysisOutput(
        resumo_perfil="Fernando, curioso em círculos.",
        etapa_sugerida=models.EtapaFunil.QUALIFICACAO,
        desfecho_sugerido=models.DesfechoLead.EM_ANDAMENTO,
        transbordo_sugerido=False,
        temperatura_sugerida=models.TemperaturaLead.FRIO,
        justificativa="Conversa longa sem decisão",
        dados_qualificacao=schemas.DadosQualificacao()
    )

    with patch("agents.analisar_lead_e_fsm", new_callable=AsyncMock) as mock_analista, \
         patch("agents.gerar_resposta_vendedor", new_callable=AsyncMock) as mock_closer, \
         patch("services.conversation_pacing_service.redis_client.incr", new_callable=AsyncMock) as mock_incr, \
         patch.object(InboundService.whatsapp_gateway, "enviar_mensagem", new_callable=AsyncMock) as mock_send, \
         patch("services.transbordo_service.TransbordoService.executar_transbordo", new_callable=AsyncMock) as mock_transbordo:

        mock_analista.return_value = analise_mock
        mock_incr.return_value = 30  # 30 mensagens na etapa (Trava FinOps)

        await InboundService._processar_cognicao_e_resposta(
            db=db_session,
            lead=lead,
            telefone=telefone,
            nome_contato="Fernando",
            texto_consolidado="Mas vocês têm integração com sistema X?",
            historico_recente=[]
        )

        # 1. Closer agent não deve ser chamado para poupar tokens
        mock_closer.assert_not_called()

        # 2. Despedida humana enviada diretamente
        mock_send.assert_awaited_once()
        _, send_kwargs = mock_send.call_args
        mensagem_enviada = mock_send.call_args[0][1] if len(mock_send.call_args[0]) > 1 else send_kwargs.get("texto")
        assert "Fernando" in mensagem_enviada
        assert "portas continuam abertas" in mensagem_enviada

        # 3. Lead atualizado no banco como PERDIDO por estagnação
        await db_session.refresh(lead)
        assert lead.desfecho == models.DesfechoLead.PERDIDO
        assert lead.temperatura == models.TemperaturaLead.FRIO
        assert "Estagnação Conversacional" in lead.motivo_perda

        # 4. Transbordo NÃO DEVE ser acionado (100% Zero-Touch)
        mock_transbordo.assert_not_called()
        assert lead.controle == models.ControleAtendimento.PILOTO_IA
