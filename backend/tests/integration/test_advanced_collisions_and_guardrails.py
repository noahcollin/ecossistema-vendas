"""
ADVANCED COLLISIONS, RACE CONDITIONS & LGPD GUARDRAILS
======================================================
Investiga e isola 4 fragilidades sofisticadas:
1. Colisão de Atendimento em Voo (In-Flight Human Collision):
   O atendente humano intervém enquanto o modelo de IA ainda está gerando a resposta.
2. Colisão de Follow-Up Ativo com Buffer Redis Não Consumido:
   O follow-up dispara para o cliente enquanto uma mensagem nova do cliente ainda está no buffer de debounce do Redis.
3. Falha de Descadastro LGPD / Anti-Spam quando a API de IA está Indisponível:
   O cliente envia comando determinístico ('PARE'/'STOP'), mas a OpenAI falha e o sistema não efetiva o opt-out.
4. Poluição e Duplicação de Tags no Lead (Case Sensitivity / Espaços vazios).
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

TEST_TEL = "+5583988880002"


async def cleanup(db, tel: str):
    lead = await LeadRepository.get_by_phone(db, tel)
    if lead:
        await FollowupRepository.cancelar_pendentes_por_lead(db, lead.id, models.StatusFollowup.ABORTADO)
        await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
        await LeadRepository.delete_lead(db, lead)
    await buffer_service.obter_e_limpar_buffer(tel)


async def test_1_in_flight_human_takeover_collision():
    print("\n--- [1/4] Testando Colisão de Atendimento em Voo (Humano Intervém durante Geração da IA) ---")
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_TEL)
        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_TEL,
            nome="Cliente Disputa Humano x IA",
            etapa_funil=models.EtapaFunil.QUALIFICACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.PILOTO_IA
        )
        lead_id = lead.id

    msg_ia_enviada = False

    async def mock_gerar_resposta_lenta(*args, **kwargs):
        # Simula latência de 200ms da OpenAI
        # Durante esse intervalo, o humano intervém no WhatsApp Web!
        async with AsyncSessionLocal() as db_human:
            lead_h = await LeadRepository.get_by_id(db_human, lead_id)
            await TransbordoService.capturar_mensagem_humana_whatsapp(
                db=db_human,
                lead=lead_h,
                texto="Oi! Aqui é o Marcos do suporte, pode falar comigo.",
                sender_name="Marcos Consultor"
            )
            print("   • [HUMANO INTERVEIO]: Atendente mandou mensagem no WhatsApp Web enquanto a IA pensava!")
        await asyncio.sleep(0.05)
        return "Olá, Seu Zé aqui da Inteligentte! Como posso ajudar?"

    async def mock_enviar_msg(telefone, texto, **kwargs):
        nonlocal msg_ia_enviada
        if "Seu Zé" in texto:
            msg_ia_enviada = True
            print(f"   • [IA ENVIOU NO WHATSAPP]: '{texto}'")
        return {"status": "sucesso", "dados": {"id": "msg_ia_123"}}

    with patch("agents.gerar_resposta_vendedor", side_effect=mock_gerar_resposta_lenta), \
         patch("integrations.uazapi.client.enviar_mensagem", side_effect=mock_enviar_msg), \
         patch("agents.analisar_lead_e_fsm", new_callable=AsyncMock) as mock_analise:

        mock_analise.return_value = schemas.LeadAnalysisOutput(
            resumo_perfil="Cliente quer saber sobre solar.",
            etapa_sugerida=models.EtapaFunil.QUALIFICACAO,
            desfecho_sugerido=models.DesfechoLead.EM_ANDAMENTO,
            transbordo_sugerido=False,
            justificativa="Qualificação normal",
            temperatura_sugerida=models.TemperaturaLead.MORNO,
            dados_qualificacao=schemas.DadosQualificacao()
        )

        async with AsyncSessionLocal() as db:
            lead_atual = await LeadRepository.get_by_id(db, lead_id)
            await InboundService._processar_cognicao_e_resposta(
                db=db,
                lead=lead_atual,
                telefone=TEST_TEL,
                nome_contato="Cliente Disputa",
                texto_consolidado="Quanto custa?",
                historico_recente=[]
            )

    async with AsyncSessionLocal() as db:
        interacoes = await LeadRepository.get_interactions(db, lead_id)
        textos_interacoes = [f"[{i.origem.value}]: {i.texto}" for i in interacoes]
        print(f"   • Interações no banco pós-conflito ({len(interacoes)}):")
        for t in textos_interacoes:
            print(f"     -> {t}")

        assert not msg_ia_enviada, "FALHA: A IA enviou mensagem mesmo após o atendente humano ter assumido a conversa em voo!"
        print("   ✅ [OK]: IA cancelou o envio ao detectar que o humano assumiu o controle em voo.")


async def test_2_followup_com_buffer_redis_nao_consumido():
    print("\n--- [2/4] Testando Disparo de Follow-up com Mensagens no Buffer Redis ---")
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_TEL)
        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_TEL,
            nome="Cliente Ativo no WhatsApp",
            etapa_funil=models.EtapaFunil.NEGOCIACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.PILOTO_IA
        )
        
        # Cria follow-up vencido
        passado = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        f_item = await FollowupRepository.criar(
            db=db,
            lead_id=lead.id,
            etapa_funil=models.EtapaFunil.NEGOCIACAO,
            tentativa=1,
            agendado_para=passado
        )

        # Simula cliente mandando mensagem no exato momento (ainda em debounce no Redis!)
        await buffer_service.adicionar_mensagem(TEST_TEL, "Olá, quero fechar a compra agora!")
        mensagens_no_buffer = await buffer_service.redis_client.lrange(f"buffer:{TEST_TEL}", 0, -1)
        print(f"   • Mensagens ativas no buffer do Redis aguardando debounce: {len(mensagens_no_buffer)}")

        disparo_followup_ocorreu = False

        async def mock_enviar_msg(telefone, texto, **kwargs):
            nonlocal disparo_followup_ocorreu
            disparo_followup_ocorreu = True
            print(f"   • [FOLLOWUP DISPARADO]: '{texto}'")
            return {"status": "sucesso", "dados": {"id": "f_123"}}

        with patch("integrations.uazapi.client.enviar_mensagem", side_effect=mock_enviar_msg), \
             patch("agents.sales_closer_agent.gerar_mensagem_followup", new_callable=AsyncMock) as m_gen:
            m_gen.return_value = "Oi, sumiu? Ainda tem interesse?"

            await FollowupService._executar_disparo_individual(db, f_item)

    assert not disparo_followup_ocorreu, "FALHA: Follow-up disparou para cliente com mensagens ativas no buffer do Redis!"
    print("   ✅ [OK]: Follow-up abortado/cancelado pois o cliente possui mensagens pendentes no buffer.")


async def test_3_opt_out_deterministico_com_falha_de_ia():
    print("\n--- [3/4] Testando Descadastro LGPD / Anti-Spam com Falha na API de IA ---")
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_TEL)
        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_TEL,
            nome="Cliente Quer Sair",
            etapa_funil=models.EtapaFunil.QUALIFICACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.PILOTO_IA
        )
        lead_id = lead.id

    # Cliente envia comando explícito de cancelamento
    msg_optout = "PARE, não quero mais receber mensagens de vocês! STOP"

    # Simula indisponibilidade total da OpenAI (504 Gateway Timeout / Network Down)
    with patch("core.openai_client.openai_client.beta.chat.completions.parse", side_effect=Exception("OpenAI 504 Gateway Timeout")):
        async with AsyncSessionLocal() as db:
            await InboundService._executar_pipeline_atendimento(
                db=db,
                telefone=TEST_TEL,
                nome_contato="Cliente Quer Sair",
                texto_consolidado=msg_optout
            )

    async with AsyncSessionLocal() as db:
        lead_final = await LeadRepository.get_by_id(db, lead_id)
        print(f"   • Opt-out registrado no banco: {lead_final.opt_out}")
        print(f"   • Desfecho do Lead: {lead_final.desfecho.value}")

        followups = await FollowupRepository.listar_por_lead(db, lead_id)
        followups_pendentes = [f for f in followups if f.status == models.StatusFollowup.PENDENTE]
        print(f"   • Follow-ups pendentes agendados: {len(followups_pendentes)}")

        assert lead_final.opt_out, "FALHA: Lead não foi marcado como opt_out no fast-path determinístico!"
        assert len(followups_pendentes) == 0, "FALHA: Follow-ups pendentes não foram cancelados no opt-out!"
        print("   ✅ [OK]: Cliente descadastrado imediatamente via guarda determinística.")


async def test_4_sincronizacao_e_limpeza_de_tags():
    print("\n--- [4/4] Testando Limpeza e Higienização de Tags do Lead ---")
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_TEL)
        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_TEL,
            nome="Cliente Tags",
            tags=["VIP"]
        )

        # Adiciona tags sujas / redundantes
        novas_tags = ["vip", "  REQUER_ATENCAO  ", "", "VIP", "Interesse_Solar"]
        tags_atualizadas = LeadRepository.sincronizar_tags(lead, adicionar=novas_tags)
        print(f"   • Tags resultantes: {tags_atualizadas}")

        tem_duplicadas = len(tags_atualizadas) != len(set(t.strip().upper() for t in tags_atualizadas if t.strip()))
        tem_espacos_ou_vazias = any(t != t.strip() or not t for t in tags_atualizadas)

        assert not tem_duplicadas, f"FALHA: Tags com duplicação de caixa detectadas: {tags_atualizadas}"
        assert not tem_espacos_ou_vazias, f"FALHA: Tags com espaços ou vazias detectadas: {tags_atualizadas}"
        assert tags_atualizadas == ["INTERESSE_SOLAR", "REQUER_ATENCAO", "VIP"]
        print("   ✅ [OK]: Tags normalizadas e deduplicadas com segurança.")


async def main():
    print("=" * 80)
    print("🔬 INVESTIGAÇÃO DE COLISÕES DE ATENDIMENTO, BUFFER DE REDIS E LGPD DETERMINÍSTICO")
    print("=" * 80)
    
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_TEL)

    await test_1_in_flight_human_takeover_collision()
    await test_2_followup_com_buffer_redis_nao_consumido()
    await test_3_opt_out_deterministico_com_falha_de_ia()
    await test_4_sincronizacao_e_limpeza_de_tags()

    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_TEL)

    print("\n" + "=" * 80)
    print("🏁 TESTES CONCLUÍDOS")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
