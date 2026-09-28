"""
Suíte de Testes de Integração: Motor de Cadência e Follow-Up Cronometrado (RF11 & RF12)
========================================================================================
Valida:
1. Ajuste de Horário Comercial (Respeito a noites, finais de semana e domingos).
2. Agendamento automático do Toque 1 (RF11).
3. Interrupção imediata por interação do cliente / Cancelamento Reativo (RF12).
4. Processamento de lote vencido, geração de mensagem do Seu Zé e agendamento da tentativa 2.
5. Esgotamento da cadência de 3 toques com transição FSM para CONGELADO_CADENCIA.
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta, time
from unittest.mock import patch, AsyncMock

# Ajusta path para importar módulos do backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
from core.config import settings
import models
import schemas
from repositories.lead_repository import LeadRepository
from repositories.followup_repository import FollowupRepository
from services.followup_service import FollowupService

TEST_PHONE_CADENCIA = "+5583997770099"

async def cleanup(telefone: str):
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, telefone)
        if lead:
            await FollowupRepository.cancelar_pendentes_por_lead(db, lead.id)
            await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
            await LeadRepository.delete_lead(db, lead)

async def test_1_horario_comercial_anti_spam():
    print("\n" + "=" * 75)
    print("⏰ [TESTE 1] Ajuste Estrito de Horário Comercial Anti-Spam")
    print("=" * 75)

    # Simula Domingo 15:00 UTC (12:00 BRT) -> Deve empurrar para Segunda-feira 08:35 BRT (11:35 UTC)
    domingo_utc = datetime(2026, 9, 27, 15, 0, 0)  # 27/09/2026 é Domingo
    ajustado_domingo = FollowupService.ajustar_para_horario_comercial(domingo_utc)
    ajustado_domingo_local = ajustado_domingo - timedelta(hours=3)
    print(f"   • Domingo enviado: {domingo_utc} UTC")
    print(f"   • Ajustado local: {ajustado_domingo_local} (Dia da semana: {ajustado_domingo_local.weekday()})")
    assert ajustado_domingo_local.weekday() == 0, "Domingo deveria ser postergado para Segunda (0)!"
    assert ajustado_domingo_local.hour == 8 and ajustado_domingo_local.minute == 35, "Deveria abrir às 08:35!"

    # Simula Terça-feira 23:30 BRT (Quarta 02:30 UTC) -> Deve empurrar para Quarta 08:35 BRT
    noite_terca_utc = datetime(2026, 9, 23, 2, 30, 0)  # 23:30 de Terça 22/09 em BRT
    ajustado_noite = FollowupService.ajustar_para_horario_comercial(noite_terca_utc)
    ajustado_noite_local = ajustado_noite - timedelta(hours=3)
    print(f"   • Noite de Terça enviada (23:30 BRT)")
    print(f"   • Ajustado local: {ajustado_noite_local}")
    assert ajustado_noite_local.hour == 8 and ajustado_noite_local.minute == 35

    # Simula Quarta-feira 14:00 BRT (17:00 UTC) -> Horário comercial válido, deve permanecer inalterado
    horario_valido_utc = datetime(2026, 9, 23, 17, 0, 0)
    ajustado_valido = FollowupService.ajustar_para_horario_comercial(horario_valido_utc)
    assert ajustado_valido == horario_valido_utc, "Horário comercial válido não deve ser alterado!"

    # Simula 3 clientes que caíram fora de hora: valida o Jitter Anti-Ban (Escalonamento Humanizado)
    cliente_0 = FollowupService.ajustar_para_horario_comercial(domingo_utc, indice_dispersao=0)
    cliente_1 = FollowupService.ajustar_para_horario_comercial(domingo_utc, indice_dispersao=1)
    cliente_2 = FollowupService.ajustar_para_horario_comercial(domingo_utc, indice_dispersao=2)
    print(f"   • [ANTI-BAN JITTER] Cliente 0 agendado para: {cliente_0 - timedelta(hours=3)}")
    print(f"   • [ANTI-BAN JITTER] Cliente 1 agendado para: {cliente_1 - timedelta(hours=3)}")
    print(f"   • [ANTI-BAN JITTER] Cliente 2 agendado para: {cliente_2 - timedelta(hours=3)}")
    assert cliente_1 > cliente_0, "Cliente 1 deve ser agendado após o Cliente 0!"
    assert cliente_2 > cliente_1, "Cliente 2 deve ser agendado após o Cliente 1!"
    diff_minutos_1 = (cliente_1 - cliente_0).total_seconds() / 60
    diff_minutos_2 = (cliente_2 - cliente_1).total_seconds() / 60
    assert diff_minutos_1 >= 3.0, f"Deveria ter ao menos 3 min de respiro, teve {diff_minutos_1:.1f}m"
    assert diff_minutos_2 >= 3.0, f"Deveria ter ao menos 3 min de respiro, teve {diff_minutos_2:.1f}m"

    print("✅ [HORÁRIO COMERCIAL & ANTI-BAN]: Jitter temporal, dispersão e janelas comerciais 100% validados!")

async def test_2_agendamento_automatico_toque_1():
    print("\n" + "=" * 75)
    print("📅 [TESTE 2] Agendamento Automático de Follow-Up (RF11 do PRD)")
    print("=" * 75)

    await cleanup(TEST_PHONE_CADENCIA)

    async with AsyncSessionLocal() as db:
        # Cria lead ativo em negociação
        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_PHONE_CADENCIA,
            nome="Dra. Beatriz",
            tipo_entrada=models.TipoEntradaLead.INBOUND,
            etapa_funil=models.EtapaFunil.NEGOCIACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.PILOTO_IA
        )
        lead.resumo_perfil = "Dra. Beatriz é proprietária de um laboratório em Campina Grande. Recebeu proposta de R$ 68.000."
        await db.commit()

        # Dispara agendamento
        followup = await FollowupService.agendar_proximo_followup(db, lead)

        assert followup is not None, "Deveria ter agendado o follow-up!"
        assert followup.tentativa == 1, f"Deveria ser tentativa 1, foi {followup.tentativa}"
        assert followup.status == models.StatusFollowup.PENDENTE
        assert followup.etapa_funil == models.EtapaFunil.NEGOCIACAO
        print(f"   • Follow-up agendado: ID {followup.id} | Tentativa {followup.tentativa}/3 | Data: {followup.agendado_para}")

        # Se tentar agendar de novo sem o anterior disparar, deve retornar o mesmo (idempotência)
        followup_duplicado = await FollowupService.agendar_proximo_followup(db, lead)
        assert followup_duplicado.id == followup.id, "Não deve duplicar agendamentos pendentes!"
        print("✅ [IDEMPOTÊNCIA & RF11]: Toque 1 agendado e idempotência garantida!")

async def test_3_cancelamento_reativo_resposta_cliente():
    print("\n" + "=" * 75)
    print("🛑 [TESTE 3] Interrupção Imediata por Interação do Cliente (RF12 do PRD)")
    print("=" * 75)

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE_CADENCIA)
        assert lead is not None

        # Confirma que há um follow-up pendente
        pendente_antes = await FollowupRepository.obter_pendente_por_lead(db, lead.id)
        assert pendente_antes is not None
        print(f"   • Status antes da resposta do cliente: {pendente_antes.status.value}")

        # Simula cliente enviando nova mensagem no WhatsApp
        qtd_cancelados = await FollowupService.cancelar_followups_pendentes(db, lead.id)
        assert qtd_cancelados >= 1, f"Deveria ter cancelado pelo menos 1 registro, cancelou {qtd_cancelados}"

        # Verifica no banco se o status virou CANCELADO_POR_RESPOSTA
        pendente_depois = await FollowupRepository.obter_pendente_por_lead(db, lead.id)
        assert pendente_depois is None, "Não deve haver nenhum follow-up pendente após resposta!"

        ultima = await FollowupRepository.obter_ultima_tentativa(db, lead.id)
        assert ultima.status == models.StatusFollowup.CANCELADO_POR_RESPOSTA
        print(f"   • Status após nova mensagem do cliente: {ultima.status.value}")
        print("✅ [CANCELAMENTO REATIVO & RF12]: Follow-up abortado instantaneamente com nova mensagem!")

async def test_4_processamento_lote_vencido_e_proximo_toque():
    print("\n" + "=" * 75)
    print("🚀 [TESTE 4] Processamento de Lote Vencido, Geração do Seu Zé e Toque 2")
    print("=" * 75)

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE_CADENCIA)
        assert lead is not None

        # Cria intencionalmente um follow-up vencido no passado (ex: 10 minutos atrás) dentro do horário comercial
        agora_utc = datetime.now(timezone.utc).replace(tzinfo=None)
        passado_utc = agora_utc - timedelta(minutes=10)

        followup_vencido = await FollowupRepository.criar(
            db=db,
            lead_id=lead.id,
            etapa_funil=lead.etapa_funil,
            tentativa=1,
            agendado_para=passado_utc
        )
        print(f"   • Follow-up vencido inserido: ID {followup_vencido.id} (Agendado para: {passado_utc})")

        # Adiciona interação prévia para o Seu Zé contextualizar
        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.IA,
            texto="Dra. Beatriz, encaminhei a proposta de R$ 68.000 com inversores bifásicos para seu e-mail. Ficou alguma dúvida?"
        )

        # Executa processamento do lote com envio simulado para número de teste
        with patch("integrations.uazapi.client.enviar_mensagem", new_callable=AsyncMock) as m_send, \
             patch("integrations.uazapi.client.enviar_presenca", new_callable=AsyncMock):
            m_send.return_value = {"status": "sucesso", "dados": {"id": "f_123"}}
            processados = await FollowupService.processar_lote_followups(db)
            assert processados >= 1, f"Deveria ter processado pelo menos 1 follow-up, processou {processados}"

        # Verifica se o follow-up 1 virou DISPARADO
        await db.refresh(followup_vencido)
        assert followup_vencido.status == models.StatusFollowup.DISPARADO
        assert followup_vencido.mensagem_disparada is not None
        print(f"   • Mensagem gerada pelo Seu Zé:\n     \"{followup_vencido.mensagem_disparada}\"")

        # Verifica se o Toque 2 foi automaticamente agendado
        toque_2 = await FollowupRepository.obter_pendente_por_lead(db, lead.id)
        assert toque_2 is not None, "Deveria ter agendado automaticamente o Toque 2!"
        assert toque_2.tentativa == 2, f"Tentativa deveria ser 2, foi {toque_2.tentativa}"
        print(f"   • Toque 2 agendado automaticamente para: {toque_2.agendado_para}")
        print("✅ [CADÊNCIA PROGRESSIVA]: Toque 1 disparado e Toque 2 agendado com sucesso!")

async def test_5_esgotamento_cadencia_e_congelamento_fsm():
    print("\n" + "=" * 75)
    print("❄️ [TESTE 5] Esgotamento de 3 Toques e Transição para CONGELADO_CADENCIA")
    print("=" * 75)

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE_CADENCIA)
        assert lead is not None

        # Cancela qualquer pendente e simula que o Toque 3 acabou de ser DISPARADO
        await FollowupRepository.cancelar_pendentes_por_lead(db, lead.id)
        agora_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        toque_3_disparado = await FollowupRepository.criar(
            db=db,
            lead_id=lead.id,
            etapa_funil=lead.etapa_funil,
            tentativa=3,
            agendado_para=agora_utc
        )
        toque_3_disparado.status = models.StatusFollowup.DISPARADO
        toque_3_disparado.mensagem_disparada = "Dra. Beatriz, vou deixar nosso contato em pausa para não atrapalhar sua rotina. Um grande abraço!"
        await db.commit()

        # Tenta agendar o próximo toque
        resultado = await FollowupService.agendar_proximo_followup(db, lead)

        # Não deve criar Toque 4 e a FSM deve mudar para CONGELADO_CADENCIA
        assert resultado is None, "Não deve agendar após o Toque 3!"
        await db.refresh(lead)
        assert lead.desfecho == models.DesfechoLead.CONGELADO_CADENCIA, f"Desfecho deveria ser CONGELADO_CADENCIA, foi {lead.desfecho}"
        assert lead.temperatura == models.TemperaturaLead.FRIO
        assert "Cadência Esgotada" in lead.motivo_perda
        print(f"   • Novo desfecho do lead: {lead.desfecho.value}")
        print(f"   • Motivo da perda registrado: {lead.motivo_perda}")
        print("✅ [FSM 4D & SEÇÃO 5.1 DO PRD]: Lead transicionado para CONGELADO_CADENCIA com sucesso!")

    await cleanup(TEST_PHONE_CADENCIA)
    print("🧹 Cleanup concluído.")

async def run_all_tests():
    print("=" * 75)
    print("🧪 INICIANDO BATERIA DE TESTES: MOTOR DE CADÊNCIA E FOLLOW-UP (RF11 & RF12)")
    print("=" * 75)

    # Configuração otimizada para suíte de testes (sem sleeps demorados)
    settings.FOLLOWUP_PACING_MIN_SECONDS = 0.05
    settings.FOLLOWUP_PACING_MAX_SECONDS = 0.1
    settings.FOLLOWUP_SIMULAR_DIGITACAO = False

    await test_1_horario_comercial_anti_spam()
    await test_2_agendamento_automatico_toque_1()
    await test_3_cancelamento_reativo_resposta_cliente()
    await test_4_processamento_lote_vencido_e_proximo_toque()
    await test_5_esgotamento_cadencia_e_congelamento_fsm()
    print("\n" + "=" * 75)
    print("🎉 TODOS OS 5 TESTES DO MOTOR DE CADÊNCIA PASSARAM COM 100% DE SUCESSO!")
    print("=" * 75)

if __name__ == "__main__":
    asyncio.run(run_all_tests())
