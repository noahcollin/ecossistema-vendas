"""
DEEP CHAOS, CONCURRENCY & SUBTLE VULNERABILITIES TEST SUITE
===========================================================
Investiga e isola fragilidades ocultas no ecossistema:
1. Atendente humano digitando no WhatsApp Web/Mobile com senderName vazio/None sendo descartado como bot.
2. Concorrência entre workers de follow-up (duplo disparo para o cliente).
3. Mensagens de Canais/Newsletters do WhatsApp (@newsletter) criando leads fantasmas.
4. Burn de tokens LLM com auditorias repetidas a cada mensagem de deal já fechado (GANHO/PERDIDO).
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

# Adiciona backend ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
from core.config import settings
import models
import schemas
from repositories.lead_repository import LeadRepository
from repositories.followup_repository import FollowupRepository
from services.lead_service import LeadService
from services.followup_service import FollowupService
from services.transbordo_service import TransbordoService
from services.inbound_service import InboundService
from integrations.redis import buffer as buffer_service
from api.routers.webhook import webhook_uazapi

TEST_TEL = "+5583988880001"


async def cleanup(db, tel: str):
    lead = await LeadRepository.get_by_phone(db, tel)
    if lead:
        await FollowupRepository.cancelar_pendentes_por_lead(db, lead.id, models.StatusFollowup.ABORTADO)
        await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
        await LeadRepository.delete_lead(db, lead)
    await buffer_service.obter_e_limpar_buffer(tel)


async def test_1_humano_sem_sender_name_no_whatsapp_web():
    print("\n--- [1/4] Testando Atendente Humano no WhatsApp Web sem senderName (fromMe=True) ---")
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_TEL)
        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_TEL,
            nome="Cliente Humano Teste",
            etapa_funil=models.EtapaFunil.QUALIFICACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.PILOTO_IA
        )

    # Simula mensagem digitada pelo atendente no WhatsApp Web / Mobile oficial:
    # fromMe=True, wasSentByApi=False, senderName=None (não preenchido pelo Baileys/WhatsApp para o próprio dono)
    payload_web = schemas.UazapiPayload(
        event="messages.upsert",
        chat=schemas.UazapiChat(phone=TEST_TEL, name="Cliente"),
        message=schemas.UazapiMessage(
            id="msg_web_humano_999",
            text="Olá! Estou assumindo aqui seu atendimento.",
            fromMe=True,
            wasSentByApi=False,
            senderName=None  # WhatsApp Web oficial não envia senderName na própria conta
        )
    )

    res = await webhook_uazapi(payload_web)
    print(f"   • Resposta do Webhook: {res}")

    async with AsyncSessionLocal() as db:
        lead_db = await LeadRepository.get_by_phone(db, TEST_TEL)
        print(f"   • Controle do Lead: {lead_db.controle.value}")
        interacoes = await LeadRepository.get_interactions(db, lead_db.id)
        origens = [i.origem.value for i in interacoes]
        print(f"   • Origens das interações gravadas: {origens}")

        assert res.get("status") in ["capturada_intervencao_humana", "iniciado_outbound_humano"], f"FALHA: Resposta inesperada: {res}"
        assert lead_db.controle == models.ControleAtendimento.HUMANO_ASSUMIU, f"FALHA: Controle esperado HUMANO_ASSUMIU, obtido {lead_db.controle}"
        assert "EM_ATENDIMENTO_HUMANO" in lead_db.tags, "FALHA: Tag EM_ATENDIMENTO_HUMANO ausente"
        assert any(o.lower() == "humano" for o in origens), f"FALHA: Nenhuma interação humana gravada: {origens}"
        print("   ✅ [PASSOU]: Intervenção humana capturada e controle assumido com sucesso!")


async def test_2_concorrencia_duplo_disparo_followup():
    print("\n--- [2/4] Testando Concorrência de Workers de Follow-Up (Anti-Duplo Disparo) ---")
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_TEL)
        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_TEL,
            nome="Cliente Risco Duplo Disparo",
            etapa_funil=models.EtapaFunil.NEGOCIACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.PILOTO_IA
        )
        
        # Cria follow-up vencido no passado
        passado = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        f_item = await FollowupRepository.criar(
            db=db,
            lead_id=lead.id,
            etapa_funil=models.EtapaFunil.NEGOCIACAO,
            tentativa=1,
            agendado_para=passado
        )
        f_id = f_item.id
        print(f"   • Follow-up criado e vencido (ID: {f_id})")

    disparos_chamados = 0

    async def mock_enviar_msg(*args, **kwargs):
        nonlocal disparos_chamados
        disparos_chamados += 1
        await asyncio.sleep(0.05)  # Latência de rede
        return {"status": "sucesso", "dados": {"id": f"msg_mock_{disparos_chamados}"}}

    # Simula dois workers executando o lote exatamente no mesmo momento
    with patch("integrations.uazapi.client.enviar_mensagem", side_effect=mock_enviar_msg), \
         patch("services.followup_service.gerar_mensagem_followup", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = "Oi! Como ficou a proposta?"

        async def rodar_worker(worker_id: int):
            async with AsyncSessionLocal() as db_worker:
                return await FollowupService.processar_lote_followups(db_worker)

        # Executa concorrentemente
        res1, res2 = await asyncio.gather(rodar_worker(1), rodar_worker(2))
        print(f"   • Worker 1 processou: {res1} | Worker 2 processou: {res2}")
        print(f"   • Total de mensagens enviadas ao WhatsApp do cliente: {disparos_chamados}")

        assert disparos_chamados == 1, f"FALHA: {disparos_chamados} mensagens disparadas! Duplo disparo ocorreu."
        assert (res1 == 1 and res2 == 0) or (res1 == 0 and res2 == 1), "FALHA: Exatamente um worker deveria ter processado."
        print("   ✅ [PASSOU]: Trava distribuída garantiu exatamente 1 disparo sem duplo envio!")


async def test_3_newsletter_e_canais_whatsapp():
    print("\n--- [3/4] Testando Invasão por Canais/Newsletters do WhatsApp (@newsletter) ---")
    canal_jid = "12036314352432@newsletter"
    
    # Em produção, SANDBOX_MODE é False
    modo_anterior = settings.SANDBOX_MODE
    settings.SANDBOX_MODE = False
    try:
        payload_canal = schemas.UazapiPayload(
            event="messages.upsert",
            chat=schemas.UazapiChat(phone=canal_jid, name="Canal de Notícias Solar"),
            message=schemas.UazapiMessage(
                id="post_canal_001",
                text="Novidade no setor de energia solar!",
                fromMe=False
            )
        )

        res = await webhook_uazapi(payload_canal)
        print(f"   • Resposta do Webhook para post de canal: {res}")

        assert res.get("status") == "ignorado", f"FALHA: Post de canal não foi ignorado: {res}"
        assert res.get("motivo") == "mensagem_de_grupo_ou_canal", f"FALHA: Motivo inesperado: {res.get('motivo')}"
        print("   ✅ [PASSOU]: Canais/Newsletters do WhatsApp filtrados com segurança!")
    finally:
        settings.SANDBOX_MODE = modo_anterior


async def test_4_burn_de_tokens_em_deal_fechado():
    print("\n--- [4/4] Testando Prevenção de Queima de Tokens em Deals Fechados ---")
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_TEL)
        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_TEL,
            nome="Cliente Compra Concluída",
            etapa_funil=models.EtapaFunil.FECHAMENTO,
            desfecho=models.DesfechoLead.GANHO,
            controle=models.ControleAtendimento.PILOTO_IA
        )
        # Salva um dossiê comercial prévio
        lead.dossie_comercial = {
            "resumo_executivo": "Cliente fechou contrato solar de 10kWp.",
            "win_loss_analise": "GANHO",
            "dica_de_ouro": "Cliente técnico, gostou de detalhes."
        }
        await db.commit()

    # O cliente manda mais mensagens após o fechamento: "Obrigado Seu Zé!", "Quando instalam?"
    # Simula o analista mantendo desfecho GANHO
    mock_analise = schemas.LeadAnalysisOutput(
        resumo_perfil="Cliente já comprou.",
        etapa_sugerida=models.EtapaFunil.FECHAMENTO,
        desfecho_sugerido=models.DesfechoLead.GANHO,
        transbordo_sugerido=False,
        justificativa="Lead tirando dúvidas de pós-venda.",
        temperatura_sugerida=models.TemperaturaLead.QUENTE,
        dados_qualificacao=schemas.DadosQualificacao()
    )

    auditorias_disparadas = 0

    async def mock_auditoria(lead_id: int):
        nonlocal auditorias_disparadas
        auditorias_disparadas += 1

    with patch("agents.analisar_lead_e_fsm", new_callable=AsyncMock) as m_an, \
         patch("agents.sales_closer_agent.gerar_resposta_vendedor", new_callable=AsyncMock) as m_resp, \
         patch("integrations.uazapi.client.enviar_mensagem", new_callable=AsyncMock), \
         patch.object(InboundService, "disparar_auditoria_background", side_effect=mock_auditoria):

        m_an.return_value = mock_analise
        m_resp.return_value = "Obrigado você! Já estamos providenciando tudo."

        async with AsyncSessionLocal() as db:
            await InboundService._processar_cognicao_e_resposta(
                db=db,
                lead=lead,
                telefone=TEST_TEL,
                nome_contato="Cliente Compra Concluída",
                texto_consolidado="Obrigado Seu Zé!",
                historico_recente=[]
            )

        print(f"   • Auditorias disparadas para mensagem pós-fechamento: {auditorias_disparadas}")
        assert auditorias_disparadas == 0, f"FALHA: {auditorias_disparadas} auditorias disparadas para deal já finalizado!"
        print("   ✅ [PASSOU]: Auditorias redundantes bloqueadas, preservando tokens de LLM!")


async def main():
    print("=" * 80)
    print("🛡️ SUÍTE DE TESTES: BLINDAGEM CONTRA DUPLO DISPARO, CANAIS E ZERO-CLICK")
    print("=" * 80)
    
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_TEL)

    await test_1_humano_sem_sender_name_no_whatsapp_web()
    await test_2_concorrencia_duplo_disparo_followup()
    await test_3_newsletter_e_canais_whatsapp()
    await test_4_burn_de_tokens_em_deal_fechado()

    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_TEL)

    print("\n" + "=" * 80)
    print("🎉 TODOS OS 4 TESTES DE BLINDAGEM PASSARAM COM 100% DE SUCESSO!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
