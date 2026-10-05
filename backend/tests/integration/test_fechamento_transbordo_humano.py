import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

import models
import schemas
from services.inbound_service import InboundService
from services.transbordo_service import TransbordoService
from integrations.transbordo_notifier import TransbordoNotifier
from repositories.lead_repository import LeadRepository


@pytest.mark.asyncio
async def test_fechamento_transbordo_humano_fluxo_completo(db_session: AsyncSession):
    """
    Testa o fluxo de 2 tempos de fechamento comercial via transbordo humano:
    Tempo 1: Lead dá sinal verde -> Etapa FECHAMENTO -> Seu Zé pede dados cadastrais e avisa do especialista.
    Tempo 2: Lead envia dados -> Seu Zé responde confirmando recebimento -> Transbordo humano é acionado
             com tags PRONTO_FECHAMENTO e AGUARDANDO_CONTRATO, sem agendar novos follow-ups automáticos.
    """
    import uuid
    telefone = f"+55119{uuid.uuid4().int % 100000000:08d}"
    lead = models.Lead(
        telefone=telefone,
        nome="Carlos Eduardo",
        etapa_funil=models.EtapaFunil.NEGOCIACAO,
        temperatura=models.TemperaturaLead.QUENTE,
        valor_estimado=3500.0,
        controle=models.ControleAtendimento.PILOTO_IA
    )
    db_session.add(lead)
    await db_session.commit()
    await db_session.refresh(lead)

    # -------------------------------------------------------------
    # TEMPO 1: Lead diz "Quero fechar!" -> Transição para FECHAMENTO
    # -------------------------------------------------------------
    analise_tempo1 = schemas.LeadAnalysisOutput(
        resumo_perfil="Carlos Eduardo, dono da Padaria Trigo. Decidiu contratar Agentes Autônomos.",
        dados_qualificacao=schemas.DadosQualificacao(solucao_interesse="AGENTES_AUTONOMOS"),
        etapa_sugerida=models.EtapaFunil.FECHAMENTO,
        desfecho_sugerido=models.DesfechoLead.EM_ANDAMENTO,
        transbordo_sugerido=False,
        justificativa="Lead deu sinal verde para fechar. Coletar dados cadastrais.",
        temperatura_sugerida=models.TemperaturaLead.QUENTE,
        valor_estimado=3500.0,
        tags_sugeridas=["sinal_verde_fechamento"]
    )

    mock_resposta_ia_tempo1 = (
        "Sensacional, Carlos! Excelente decisão! Para eu já organizar tudo e o nosso especialista "
        "responsável por contratos te chamar para formalizarmos a assinatura, me passa por favor: "
        "a Razão Social, o CNPJ ou CPF e o seu melhor e-mail."
    )

    with patch("agents.analisar_lead_e_fsm", new_callable=AsyncMock) as mock_analista, \
         patch("agents.gerar_resposta_vendedor", new_callable=AsyncMock) as mock_closer, \
         patch.object(InboundService.whatsapp_gateway, "enviar_mensagem_humanizada", new_callable=AsyncMock) as mock_whatsapp, \
         patch.object(InboundService.whatsapp_gateway, "enviar_presenca", new_callable=AsyncMock):

        mock_analista.return_value = analise_tempo1
        mock_closer.return_value = mock_resposta_ia_tempo1
        mock_whatsapp.return_value = ([mock_resposta_ia_tempo1], True)

        await InboundService._processar_cognicao_e_resposta(
            db=db_session,
            lead=lead,
            telefone=telefone,
            nome_contato="Carlos",
            texto_consolidado="Excelente proposta! Quero fechar sim, como fazemos?",
            historico_recente=[]
        )

    # Verificações Tempo 1:
    lead_recarregado = await LeadRepository.get_by_id(db_session, lead.id)
    assert lead_recarregado.etapa_funil == models.EtapaFunil.FECHAMENTO
    assert lead_recarregado.controle == models.ControleAtendimento.PILOTO_IA  # IA ainda no comando para coletar
    assert mock_whatsapp.called
    assert "especialista" in mock_resposta_ia_tempo1

    # -------------------------------------------------------------
    # TEMPO 2: Lead envia os dados cadastrais
    # -------------------------------------------------------------
    analise_tempo2 = schemas.LeadAnalysisOutput(
        resumo_perfil="Carlos Eduardo, Padaria Trigo Ltda, CNPJ: 12.345.678/0001-90, email: financeiro@trigo.com.br",
        dados_qualificacao=schemas.DadosQualificacao(
            solucao_interesse="AGENTES_AUTONOMOS",
            dados_cadastrais="CNPJ 12.345.678/0001-90"
        ),
        etapa_sugerida=models.EtapaFunil.FECHAMENTO,
        desfecho_sugerido=models.DesfechoLead.EM_ANDAMENTO,
        transbordo_sugerido=True,
        justificativa="Fechamento Comercial / Assinatura de Contrato",
        temperatura_sugerida=models.TemperaturaLead.QUENTE,
        valor_estimado=3500.0,
        tags_sugeridas=["dados_recebidos"]
    )

    mock_resposta_ia_tempo2 = (
        "Perfeito, Carlos! Já anotei todos os seus dados e repassei agora mesmo para o nosso colega "
        "de contratos e implantação. Ele já está cuidando da sua minuta e vai te chamar por aqui em instantes. "
        "Um grande abraço e seja muito bem-vindo!"
    )

    with patch("agents.analisar_lead_e_fsm", new_callable=AsyncMock) as mock_analista, \
         patch("agents.gerar_resposta_vendedor", new_callable=AsyncMock) as mock_closer, \
         patch.object(InboundService.whatsapp_gateway, "enviar_mensagem_humanizada", new_callable=AsyncMock) as mock_whatsapp, \
         patch.object(InboundService.whatsapp_gateway, "enviar_presenca", new_callable=AsyncMock), \
         patch.object(TransbordoService, "notificar_equipe", new_callable=AsyncMock) as mock_notificar, \
         patch("services.followup_service.FollowupService.agendar_proximo_followup", new_callable=AsyncMock) as mock_followup:

        mock_analista.return_value = analise_tempo2
        mock_closer.return_value = mock_resposta_ia_tempo2
        mock_whatsapp.return_value = ([mock_resposta_ia_tempo2], True)

        await InboundService._processar_cognicao_e_resposta(
            db=db_session,
            lead=lead_recarregado,
            telefone=telefone,
            nome_contato="Carlos",
            texto_consolidado="Razão Social: Padaria Trigo Ltda, CNPJ: 12.345.678/0001-90, email: financeiro@trigo.com.br",
            historico_recente=[]
        )
        import asyncio
        await asyncio.sleep(0.05)

    # Verificações Tempo 2:
    lead_final = await LeadRepository.get_by_id(db_session, lead.id)
    # 1. Mensagem de acolhimento do Seu Zé FOI ENVIADA antes do silenciamento
    assert mock_whatsapp.called
    # 2. Atendimento foi escalado para TRANSBORDO_SOLICITADO
    assert lead_final.controle == models.ControleAtendimento.TRANSBORDO_SOLICITADO
    # 3. Tags de fechamento foram aplicadas
    assert "PRONTO_FECHAMENTO" in lead_final.tags
    assert "AGUARDANDO_CONTRATO" in lead_final.tags
    assert "TRANSBORDO" in lead_final.tags
    # 4. Nenhum followup automático foi agendado para o Seu Zé (passagem limpa para humano)
    assert not mock_followup.called
    # 5. Notificação de equipe disparada
    assert mock_notificar.called


@pytest.mark.asyncio
async def test_notificacao_vip_fechamento_template():
    """Valida que o alerta do supervisor usa o template VIP de contrato."""
    lead = models.Lead(
        id=999,
        nome="Mariana Costa",
        telefone="+5511988887777",
        etapa_funil=models.EtapaFunil.FECHAMENTO,
        temperatura=models.TemperaturaLead.QUENTE,
        valor_estimado=4800.0,
        resumo_perfil="Clínica Sorriso, CNPJ 98.765.432/0001-10, email contato@sorriso.com.br"
    )

    alerta = TransbordoNotifier.formatar_alerta_supervisor(
        lead=lead,
        motivo="Fechamento Comercial / Assinatura de Contrato"
    )

    assert "OPORTUNIDADE QUENTE: LEAD PRONTO PARA ASSINATURA DE CONTRATO" in alerta
    assert "Mariana Costa" in alerta
    assert "R$ 4,800.00" in alerta
    assert "Prepare a minuta" in alerta
