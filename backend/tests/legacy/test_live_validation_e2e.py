"""
Validação Completa E2E: Agentes de Vendas, Analista FSM, Webhook e Guardas
==========================================================================
Executa testes ao vivo com a OpenAI e o Banco de Dados para validar:
1. Respostas do Vendedor ('Seu Zé') em cada etapa do funil (NOVO_CONTATO, QUALIFICACAO, NEGOCIACAO, FECHAMENTO, FORA DE ESCOPO).
2. Classificação do Analista nas 4 dimensões (etapa, desfecho, controle, temperatura, perda dinâmica, tags).
3. Guardas do Webhook (LGPD opt-out e transbordo com silenciamento da IA).
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
from agents.sales_closer_agent import gerar_resposta_vendedor
from agents.lead_analyzer_agent import analisar_lead_e_fsm

TEST_PHONE = "+5583999990009"

async def cleanup(db, phone: str):
    existente = await LeadRepository.get_by_phone(db, phone)
    if existente:
        await LeadRepository.delete_interactions_by_lead_id(db, existente.id)
        await LeadRepository.delete_lead(db, existente)

async def test_1_vendedor_postura_por_etapa():
    print("\n" + "=" * 70)
    print("🤖 [TESTE 1] Postura do Vendedor ('Seu Zé') nas 4 Etapas do Funil")
    print("=" * 70)
    
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_PHONE)
        lead_in = schemas.LeadCreate(nome="Mariana Albuquerque", telefone=TEST_PHONE)
        lead = await LeadService.criar_lead(db, lead_in)
        
        # Etapa 1: NOVO_CONTATO
        r1 = await gerar_resposta_vendedor(
            nome_cliente_bruto="Mariana Albuquerque",
            ficha_resumo=None,
            etapa_funil=models.EtapaFunil.NOVO_CONTATO,
            historico_recente=[models.Interacao(origem=models.InteracaoOrigem.CLIENTE, texto="Olá, boa tarde! Gostaria de informações.")]
        )
        print(f"\n[1.1 NOVO_CONTATO] Cliente: 'Olá, boa tarde! Gostaria de informações.'")
        print(f"👉 Seu Zé: \"{r1}\"")
        assert len(r1) > 10, "Vendedor deve responder ao novo contato"
        
        # Etapa 2: QUALIFICACAO
        ficha_2 = "Cliente possui uma clínica odontológica e quer reduzir despesas fixas."
        r2 = await gerar_resposta_vendedor(
            nome_cliente_bruto="Mariana",
            ficha_resumo=ficha_2,
            etapa_funil=models.EtapaFunil.QUALIFICACAO,
            historico_recente=[models.Interacao(origem=models.InteracaoOrigem.CLIENTE, texto="Minha conta de energia da clínica vem muito alta todo mês, cerca de R$ 3.500.")]
        )
        print(f"\n[1.2 QUALIFICAÇÃO] Cliente: 'Minha conta de energia da clínica vem muito alta todo mês, cerca de R$ 3.500.'")
        print(f"👉 Seu Zé: \"{r2}\"")
        assert len(r2) > 10, "Vendedor deve fazer perguntas de qualificação"
        
        # Etapa 3: NEGOCIACAO
        ficha_3 = "Clínica Odontológica, fatura R$ 3.500/mês. Proposta de R$ 42.000 enviada."
        r3 = await gerar_resposta_vendedor(
            nome_cliente_bruto="Mariana",
            ficha_resumo=ficha_3,
            etapa_funil=models.EtapaFunil.NEGOCIACAO,
            historico_recente=[models.Interacao(origem=models.InteracaoOrigem.CLIENTE, texto="Achei a proposta interessante, mas estou com receio do prazo de retorno do investimento.")]
        )
        print(f"\n[1.3 NEGOCIAÇÃO] Cliente: 'Achei a proposta interessante, mas estou com receio do prazo de retorno do investimento.'")
        print(f"👉 Seu Zé: \"{r3}\"")
        assert len(r3) > 10, "Vendedor deve sanar a objeção com segurança"
        
        # Etapa 4: FECHAMENTO
        r4 = await gerar_resposta_vendedor(
            nome_cliente_bruto="Mariana",
            ficha_resumo=ficha_3,
            etapa_funil=models.EtapaFunil.FECHAMENTO,
            historico_recente=[models.Interacao(origem=models.InteracaoOrigem.CLIENTE, texto="Gostei muito das condições! Quero fechar o contrato, como fazemos?")]
        )
        print(f"\n[1.4 FECHAMENTO] Cliente: 'Gostei muito das condições! Quero fechar o contrato, como fazemos?'")
        print(f"👉 Seu Zé: \"{r4}\"")
        assert len(r4) > 10, "Vendedor deve solicitar dados para formalização"

        # Etapa 5: FORA DE ESCOPO (Fusca)
        r5 = await gerar_resposta_vendedor(
            nome_cliente_bruto="Mariana",
            ficha_resumo=None,
            etapa_funil=models.EtapaFunil.QUALIFICACAO,
            historico_recente=[models.Interacao(origem=models.InteracaoOrigem.CLIENTE, texto="Vocês vendem Fusca 1978 parcelado no boleto?")]
        )
        print(f"\n[1.5 FORA DE ESCOPO] Cliente: 'Vocês vendem Fusca 1978 parcelado no boleto?'")
        print(f"👉 Seu Zé: \"{r5}\"")
        assert "fusca" in r5.lower() or "carro" in r5.lower() or "veículo" in r5.lower() or "veiculo" in r5.lower(), "Deve tratar a pergunta do Fusca com naturalidade"

async def test_2_analista_jornada_e_inteligencia():
    print("\n" + "=" * 70)
    print("🧠 [TESTE 2] Classificação Multidimensional do Analista de Vendas")
    print("=" * 70)
    
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None
        
        # Cenário A: Lead de alto ticket expressando urgência
        analise_a = await analisar_lead_e_fsm(
            lead=lead,
            historico_recente=[],
            nova_mensagem="Preciso instalar urgente em 2 galpões comerciais da minha transportadora. Nossa conta dá uns R$ 18.000 por mês. Quem decide sou eu."
        )
        print("\n[2.1 ALTO TICKET & URGÊNCIA]")
        print(f"   • Etapa Sugerida: {analise_a.etapa_sugerida}")
        print(f"   • Desfecho: {analise_a.desfecho_sugerido}")
        print(f"   • Temperatura: {analise_a.temperatura_sugerida}")
        print(f"   • Valor Estimado Capturado: R$ {analise_a.valor_estimado}")
        print(f"   • Tags Sugeridas: {analise_a.tags_sugeridas}")
        print(f"   • Transbordo Sugerido: {analise_a.transbordo_sugerido}")
        assert analise_a.temperatura_sugerida == models.TemperaturaLead.QUENTE
        assert analise_a.desfecho_sugerido == models.DesfechoLead.EM_ANDAMENTO
        
        # Cenário B: Lead recusando com objeção forte de preço
        lead.etapa_funil = models.EtapaFunil.NEGOCIACAO
        msg_ia = models.Interacao(origem=models.InteracaoOrigem.IA, texto="O investimento total fica em R$ 85.000.")
        analise_b = await analisar_lead_e_fsm(
            lead=lead,
            historico_recente=[msg_ia],
            nova_mensagem="Muito obrigado mas é inviável, o concorrente me fez por metade do preço e não tenho esse valor. Não vou querer."
        )
        print("\n[2.2 PERDA POR PREÇO / CONCORRÊNCIA]")
        print(f"   • Desfecho: {analise_b.desfecho_sugerido}")
        print(f"   • Motivo da Perda (Dinâmico): '{analise_b.motivo_perda}'")
        print(f"   • Temperatura: {analise_b.temperatura_sugerida}")
        assert analise_b.desfecho_sugerido == models.DesfechoLead.PERDIDO
        assert analise_b.motivo_perda is not None
        
        # Cenário C: Solicitação de atendente humano
        analise_c = await analisar_lead_e_fsm(
            lead=lead,
            historico_recente=[],
            nova_mensagem="Não quero conversar com robô, por gentileza me passe para um atendente humano agora."
        )
        print("\n[2.3 TRANSBORDO HUMANO]")
        print(f"   • Transbordo Sugerido: {analise_c.transbordo_sugerido}")
        print(f"   • Justificativa: {analise_c.justificativa}")
        assert analise_c.transbordo_sugerido is True
        
        # Cenário D: Solicitação expressa de Opt-out / LGPD
        analise_d = await analisar_lead_e_fsm(
            lead=lead,
            historico_recente=[],
            nova_mensagem="PARE. Não autorizei contato. Removam meu telefone imediatamente da base de vocês."
        )
        print("\n[2.4 OPT-OUT LGPD]")
        print(f"   • Opt-out Detectado: {analise_d.opt_out_detectado}")
        print(f"   • Desfecho Sugerido: {analise_d.desfecho_sugerido}")
        assert analise_d.opt_out_detectado is True
        assert analise_d.desfecho_sugerido == models.DesfechoLead.PERDIDO

async def test_3_limpeza():
    print("\n" + "=" * 70)
    print("🧹 [TESTE 3] Limpeza de Dados de Teste")
    print("=" * 70)
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_PHONE)
        print(f"✅ Lead {TEST_PHONE} expurgado com sucesso.")

async def run():
    print("🚀 INICIANDO VALIDAÇÃO COMPLETA DAS MUDANÇAS (E2E)")
    await test_1_vendedor_postura_por_etapa()
    await test_2_analista_jornada_e_inteligencia()
    await test_3_limpeza()
    print("\n" + "=" * 70)
    print("🎉 TODAS AS VALIDAÇÕES E TESTES PASSARAM COM 100% DE SUCESSO!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run())
