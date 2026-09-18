"""
Suíte de Testes Automatizados para a Máquina de Estados Multidimensional de Leads
================================================================================
Testa os 4 eixos ortogonais:
1. Etapa do Funil (NOVO_CONTATO, QUALIFICACAO, NEGOCIACAO, FECHAMENTO)
2. Desfecho do Lead (EM_ANDAMENTO, GANHO, PERDIDO, CONGELADO_CADENCIA)
3. Controle do Atendimento (PILOTO_IA, TRANSBORDO_SOLICITADO, HUMANO_ASSUMIU)
4. Inteligência de Vendas (Temperatura, Motivo Perda Dinâmico, Valor Estimado, Tags, Opt-out)
"""

import asyncio
import os
import sys

# Adiciona backend ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
import models
import schemas
from repositories.lead_repository import LeadRepository
from services.lead_service import LeadService
from services.agents.lead_analyzer_agent import analisar_lead_e_fsm

TEST_PHONE = "+5583999990001"

async def cleanup_test_lead(db, phone: str):
    existente = await LeadRepository.get_by_phone(db, phone)
    if existente:
        await LeadRepository.delete_interactions_by_lead_id(db, existente.id)
        await LeadRepository.delete_lead(db, existente)

async def test_lead_initial_multidimensional_state():
    print("\n--- [1/5] Testando Estado Inicial Multidimensional ---")
    async with AsyncSessionLocal() as db:
        await cleanup_test_lead(db, TEST_PHONE)
        
        lead_in = schemas.LeadCreate(nome="Cliente Teste FSM", telefone=TEST_PHONE)
        lead = await LeadService.criar_lead(db, lead_in)
        
        assert lead.id is not None
        assert lead.etapa_funil == models.EtapaFunil.NOVO_CONTATO
        assert lead.desfecho == models.DesfechoLead.EM_ANDAMENTO
        assert lead.controle == models.ControleAtendimento.PILOTO_IA
        assert lead.temperatura == models.TemperaturaLead.FRIO
        assert lead.motivo_perda is None
        assert lead.valor_estimado is None
        assert lead.tags == [] or lead.tags is None
        assert lead.opt_out is False
        print("✅ Estado inicial padrão com 4 dimensões validado!")

async def test_multidimensional_transitions_in_repository():
    print("\n--- [2/5] Testando Transições e Ortogonalidade no Repositório ---")
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None
        
        # 1. Avanço para Qualificação
        lead = await LeadRepository.update_multidimensional(
            db, lead,
            etapa_funil=models.EtapaFunil.QUALIFICACAO,
            temperatura=models.TemperaturaLead.MORNO,
            tags=["B2B"]
        )
        assert lead.etapa_funil == models.EtapaFunil.QUALIFICACAO
        assert lead.temperatura == models.TemperaturaLead.MORNO
        assert "B2B" in lead.tags
        assert lead.desfecho == models.DesfechoLead.EM_ANDAMENTO
        
        # 2. Avanço para Negociação com valor estimado
        lead = await LeadRepository.update_multidimensional(
            db, lead,
            etapa_funil=models.EtapaFunil.NEGOCIACAO,
            temperatura=models.TemperaturaLead.QUENTE,
            valor_estimado=45000.0,
            tags=["B2B", "Prioridade-Alta"]
        )
        assert lead.etapa_funil == models.EtapaFunil.NEGOCIACAO
        assert lead.temperatura == models.TemperaturaLead.QUENTE
        assert lead.valor_estimado == 45000.0
        assert len(lead.tags) == 2
        
        # 3. Ortogonalidade: Lead perde a negociação (PREÇO)
        # IMPORTANTE: etapa_funil permanece NEGOCIACAO para sabermos onde foi perdido!
        lead = await LeadRepository.update_multidimensional(
            db, lead,
            desfecho=models.DesfechoLead.PERDIDO,
            motivo_perda="Preço Alto",
            temperatura=models.TemperaturaLead.FRIO
        )
        assert lead.desfecho == models.DesfechoLead.PERDIDO
        assert lead.motivo_perda == "Preço Alto"
        assert lead.etapa_funil == models.EtapaFunil.NEGOCIACAO, "A etapa_funil deve ser preservada ao marcar desfecho PERDIDO!"
        
        # 4. Transbordo Humano
        lead = await LeadRepository.update_multidimensional(
            db, lead,
            controle=models.ControleAtendimento.TRANSBORDO_SOLICITADO
        )
        assert lead.controle == models.ControleAtendimento.TRANSBORDO_SOLICITADO
        
        # 5. LGPD Opt-out
        lead = await LeadRepository.update_multidimensional(
            db, lead,
            opt_out=True
        )
        assert lead.opt_out is True
        print("✅ Ortogonalidade e persistência das 4 dimensões no Repositório validadas!")

async def test_lead_analyzer_ai_prompts_and_dimensions():
    print("\n--- [3/5] Testando Analisador de IA (LeadAnalyzerAgent) ---")
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None
        
        # Reseta estado para evitar vazamento de estado do teste 2 anterior
        lead = await LeadRepository.update_multidimensional(
            db, lead,
            etapa_funil=models.EtapaFunil.NOVO_CONTATO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            temperatura=models.TemperaturaLead.FRIO,
            controle=models.ControleAtendimento.PILOTO_IA,
            opt_out=False
        )

        # Teste A: Mensagem de qualificação / interesse
        analise_interesse = await analisar_lead_e_fsm(
            lead=lead,
            historico_recente=[],
            nova_mensagem="Gostaria de saber como funciona o serviço e os valores para minha empresa de 20 funcionários."
        )
        print(f"   [IA Analise Interesse]: Etapa={analise_interesse.etapa_sugerida}, Desfecho={analise_interesse.desfecho_sugerido}, Temp={analise_interesse.temperatura_sugerida}, Tags={analise_interesse.tags_sugeridas}")
        assert analise_interesse.etapa_sugerida in [models.EtapaFunil.QUALIFICACAO, models.EtapaFunil.NEGOCIACAO]
        assert analise_interesse.desfecho_sugerido == models.DesfechoLead.EM_ANDAMENTO
        assert analise_interesse.temperatura_sugerida in [models.TemperaturaLead.MORNO, models.TemperaturaLead.QUENTE]
        
        # Teste B: Mensagem de rejeição por preço
        msg_vendedor = models.Interacao(origem=models.InteracaoOrigem.IA, texto="O pacote fica por R$ 5.000.")
        analise_perda = await analisar_lead_e_fsm(
            lead=lead,
            historico_recente=[msg_vendedor],
            nova_mensagem="Ficou muito caro para o meu orçamento, não tenho condições no momento. Vou cancelar."
        )
        print(f"   [IA Analise Perda]: Desfecho={analise_perda.desfecho_sugerido}, Motivo={analise_perda.motivo_perda}, Temp={analise_perda.temperatura_sugerida}")
        assert analise_perda.desfecho_sugerido == models.DesfechoLead.PERDIDO
        assert analise_perda.motivo_perda is not None and len(analise_perda.motivo_perda) > 0
        
        # Teste C: Solicitação de atendente humano
        analise_transbordo = await analisar_lead_e_fsm(
            lead=lead,
            historico_recente=[],
            nova_mensagem="Quero falar com um humano, por favor me transfira para um atendente."
        )
        print(f"   [IA Analise Transbordo]: Transbordo={analise_transbordo.transbordo_sugerido}")
        assert analise_transbordo.transbordo_sugerido is True
        
        # Teste D: Opt-out LGPD
        analise_optout = await analisar_lead_e_fsm(
            lead=lead,
            historico_recente=[],
            nova_mensagem="Por favor PARE de mandar mensagens. Me remova da lista!"
        )
        print(f"   [IA Analise Opt-out]: Opt-out={analise_optout.opt_out_detectado}")
        assert analise_optout.opt_out_detectado is True
        print("✅ Analisador de IA classificou perfeitamente as 4 dimensões e intenções!")

async def test_lead_service_reset_dimensions():
    print("\n--- [4/5] Testando Reset Multidimensional via LeadService ---")
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None
        
        # Modifica campos para valores não-padrão
        await LeadRepository.update_multidimensional(
            db, lead,
            etapa_funil=models.EtapaFunil.FECHAMENTO,
            desfecho=models.DesfechoLead.GANHO,
            controle=models.ControleAtendimento.HUMANO_ASSUMIU,
            temperatura=models.TemperaturaLead.QUENTE,
            motivo_perda="Nenhum",
            valor_estimado=100000.0,
            tags=["Fechado"],
            opt_out=True
        )
        
        # Executa limpeza de histórico
        resultado = await LeadService.limpar_historico_conversa(db, lead.id)
        assert resultado["status"] == "historico_limpo"
        
        lead_resetado = await LeadRepository.get_by_id(db, lead.id)
        assert lead_resetado.etapa_funil == models.EtapaFunil.NOVO_CONTATO
        assert lead_resetado.desfecho == models.DesfechoLead.EM_ANDAMENTO
        assert lead_resetado.controle == models.ControleAtendimento.PILOTO_IA
        assert lead_resetado.temperatura == models.TemperaturaLead.FRIO
        assert lead_resetado.motivo_perda is None
        assert lead_resetado.valor_estimado is None
        assert lead_resetado.tags == []
        assert lead_resetado.opt_out is False
        print("✅ LeadService.limpar_historico_conversa restaurou todas as 4 dimensões!")

async def test_cleanup():
    print("\n--- [5/5] Limpeza de Dados de Teste ---")
    async with AsyncSessionLocal() as db:
        await cleanup_test_lead(db, TEST_PHONE)
        assert await LeadRepository.get_by_phone(db, TEST_PHONE) is None
    print("✅ Lead de teste limpo com sucesso!")

async def run_all():
    print("======================================================================")
    print("🎯 INICIANDO TESTES DA ARQUITETURA MULTIDIMENSIONAL DE LEADS")
    print("======================================================================")
    await test_lead_initial_multidimensional_state()
    await test_multidimensional_transitions_in_repository()
    await test_lead_analyzer_ai_prompts_and_dimensions()
    await test_lead_service_reset_dimensions()
    await test_cleanup()
    print("\n======================================================================")
    print("🎉 TODAS AS DIMENSÕES DA FSM E INTELIGÊNCIA FORAM VALIDADAS COM SUCESSO!")
    print("======================================================================")

if __name__ == "__main__":
    asyncio.run(run_all())
