"""
ADVANCED EDGE CASES, CONCURRENCY & RESILIENCE PROBING
=====================================================
Testa e valida correções para os seguintes casos de borda:
1. Truncamento de precisão IEEE 754 em tokens de nanosegundos no Redis.
2. Follow-ups órfãos remanescentes após reset/limpeza de conversa no LeadService.
3. Resiliência do motor de follow-up quando o gateway WhatsApp falha.
4. Tratamento informativo de áudio inaudível, vazio ou mudo com fallback para o agente.
"""

import asyncio
import os
import sys
import json
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
from services.inbound_service import InboundService
from integrations.redis import buffer as buffer_service

TEST_PHONE = "+5583922220001"


async def cleanup(db, tel: str):
    lead = await LeadRepository.get_by_phone(db, tel)
    if lead:
        await FollowupRepository.cancelar_pendentes_por_lead(db, lead.id, models.StatusFollowup.ABORTADO)
        await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
        await LeadRepository.delete_lead(db, lead)
    await buffer_service.obter_e_limpar_buffer(tel)


async def test_1_redis_nanosecond_precision():
    print("\n--- [1/4] Testando Precisão Estrita em Tokens de Nanosegundos no Redis ---")
    tel = TEST_PHONE
    
    token_1 = "1790106288829767443"
    token_2 = "1790106288829767444"
    
    # Grava o token_2 no Redis (ele é a mensagem mais recente)
    chave_tempo = f"last_msg_time:{tel}"
    await buffer_service.redis_client.set(chave_tempo, token_2)
    
    # Pergunta se o token_1 (mais antigo) é o último
    eh_ultimo_t1 = await buffer_service.verificar_se_e_ultima(tel, token_1)
    print(f"   • Token 1 ({token_1}) avaliado como último? {eh_ultimo_t1}")
    assert eh_ultimo_t1 is False, "FALHA: Token antigo foi erroneamente avaliado como último devido a perda de precisão float!"

    # Pergunta se o token_2 (atual) é o último
    eh_ultimo_t2 = await buffer_service.verificar_se_e_ultima(tel, token_2)
    print(f"   • Token 2 ({token_2}) avaliado como último? {eh_ultimo_t2}")
    assert eh_ultimo_t2 is True, "FALHA: Token 2 deveria ser avaliado como o último!"

    print("   ✅ [PASSOU]: Nanosegundos comparados com exatidão estrita sem float truncation.")


async def test_2_followup_orfao_apos_limpar_conversa():
    print("\n--- [2/4] Testando Cancelamento de Follow-ups na Limpeza de Conversa ---")
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_PHONE)
        
        # 1. Cria lead em NEGOCIAÇÃO
        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_PHONE,
            nome="Cliente Com Followup",
            etapa_funil=models.EtapaFunil.NEGOCIACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO
        )
        
        # 2. Agenda follow-up
        f_item = await FollowupService.agendar_proximo_followup(db, lead)
        assert f_item is not None
        print(f"   • Follow-up agendado (ID: {f_item.id}, Etapa: {f_item.etapa_funil.value})")

        # 3. Limpa conversa
        res_limpeza = await LeadService.limpar_historico_conversa(db, lead.id)
        print(f"   • Conversa limpa: {res_limpeza['status']}")

        # 4. Verifica se ainda existe follow-up PENDENTE
        pendente = await FollowupRepository.obter_pendente_por_lead(db, lead.id)
        assert pendente is None, f"FALHA: Follow-up ID {pendente.id} continua PENDENTE como órfão!"

        # 5. Verifica se o item anterior foi marcado como ABORTADO
        await db.refresh(f_item)
        assert f_item.status == models.StatusFollowup.ABORTADO, f"FALHA: Status esperado ABORTADO, obtido {f_item.status}"
        print("   ✅ [PASSOU]: Follow-ups cancelados atômica e confiavelmente ao limpar conversa.")


async def test_3_resiliencia_a_falha_de_envio_no_followup():
    print("\n--- [3/4] Testando Resiliência quando o Gateway WhatsApp Falha ---")
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_PHONE)
        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_PHONE,
            nome="Cliente Gateway Offline",
            etapa_funil=models.EtapaFunil.QUALIFICACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO
        )
        f_item = await FollowupService.agendar_proximo_followup(db, lead)
        assert f_item is not None

        # Simula falha no envio da Uazapi (ex: número sem WhatsApp ou API indisponível)
        with patch("integrations.uazapi.client.enviar_mensagem", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = {"status": "erro", "detalhe": "WhatsApp Server Error 500"}
            
            sucesso = await FollowupService._executar_disparo_individual(db, f_item)
            print(f"   • Retorno da execução: {sucesso}")
            assert sucesso is False, "FALHA: Disparo deveria retornar False quando o gateway falha."

            await db.refresh(f_item)
            print(f"   • Status no banco: {f_item.status.value}")
            assert f_item.status != models.StatusFollowup.DISPARADO, "FALHA: Follow-up marcado como DISPARADO indevidamente!"

            interacoes = await LeadRepository.get_interactions(db, lead.id)
            print(f"   • Interações gravadas: {len(interacoes)}")
            assert len(interacoes) == 0, "FALHA: Interação gravada para mensagem que falhou no gateway!"

        print("   ✅ [PASSOU]: Falha de gateway tratada sem falso positivo de disparo.")


async def test_4_audio_silencioso_ou_vazio():
    print("\n--- [4/4] Testando Tratamento de Áudio Inaudível ou Mudo ---")
    tel = TEST_PHONE
    await buffer_service.obter_e_limpar_buffer(tel)

    msg_audio_vazio = schemas.UazapiMessage(
        messageType="audio",
        fileURL="https://exemplo.com/audio_silencioso.mp3"
    )

    # Enfileira o áudio no Redis
    await buffer_service.adicionar_mensagem(tel, msg_audio_vazio.model_dump_json())

    # Simula download retornando sem dados decodificáveis
    with patch("integrations.media.handlers.audio_handler.baixar_arquivo", new_callable=AsyncMock) as mock_dl:
        mock_dl.return_value = {"base64Data": ""}

        texto = await InboundService._consolidar_mensagens_buffer(tel)
        print(f"   • Texto consolidado resultante: '{texto}'")
        assert texto is not None, "FALHA: Áudio inaudível não deveria ser descartado como None"
        assert "ÁUDIO INAUDÍVEL" in texto, f"FALHA: Mensagem de fallback esperada, obtido: {texto}"

    print("   ✅ [PASSOU]: Áudio sem som gera fallback informativo para o agente de IA.")


async def main():
    print("=" * 75)
    print("🛡️ SUÍTE DE TESTES: CASOS DE BORDA, RESILIÊNCIA E CONCORRÊNCIA")
    print("=" * 75)
    
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_PHONE)

    await test_1_redis_nanosecond_precision()
    await test_2_followup_orfao_apos_limpar_conversa()
    await test_3_resiliencia_a_falha_de_envio_no_followup()
    await test_4_audio_silencioso_ou_vazio()

    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_PHONE)

    print("\n" + "=" * 75)
    print("🎉 TODOS OS 4 TESTES DE RESILIÊNCIA E CASOS DE BORDA PASSARAM COM SUCESSO!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(main())
