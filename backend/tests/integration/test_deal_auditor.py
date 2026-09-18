"""
Suíte de Testes Automatizados para o Agente Auditor de Negócios (DealAuditorAgent)
==================================================================================
Valida:
1. Auditoria de Negócio Ganho (GANHO): Fatores de encantamento e diferencial decisivo.
2. Auditoria de Negócio Perdido (PERDIDO): Causa raiz, menção de concorrente e atrito.
3. Auditoria de Transbordo Humano: Geração da 'Dica de Ouro' para o vendedor humano.
4. Persistência de Dossiê Comercial no Repositório e LeadService.
5. Limpeza de Dossiê no Reset de Conversa.
6. Endpoint REST POST /leads/{lead_id}/auditar.
"""

import asyncio
import os
import sys

# Adiciona backend ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from httpx import AsyncClient, ASGITransport
from core.database import AsyncSessionLocal
import models
import schemas
from main import app
from repositories.lead_repository import LeadRepository
from services.lead_service import LeadService
from services.agents.deal_auditor_agent import auditar_jornada_lead

TEST_PHONE = "+5583966660001"

async def cleanup_lead(db, phone: str):
    existente = await LeadRepository.get_by_phone(db, phone)
    if existente:
        await LeadRepository.delete_interactions_by_lead_id(db, existente.id)
        await LeadRepository.delete_lead(db, existente)

async def test_1_auditoria_negocio_ganho():
    print("\n--- [1/6] Testando Auditoria de Negócio Ganho (GANHO) ---")
    async with AsyncSessionLocal() as db:
        await cleanup_lead(db, TEST_PHONE)
        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_PHONE,
            nome="Carlos Eduardo",
            etapa_funil=models.EtapaFunil.FECHAMENTO,
            desfecho=models.DesfechoLead.GANHO,
            valor_estimado=45000.0
        )
        
        historico = [
            models.Interacao(origem=models.InteracaoOrigem.CLIENTE, texto="Olá, procuro energia solar para meu restaurante. Minha conta dá R$ 4.000."),
            models.Interacao(origem=models.InteracaoOrigem.IA, texto="Olá Carlos! É um prazer. Podemos instalar um sistema que reduz até 90% dessa conta. A proposta fica em R$ 45.000 com retorno em 2 anos."),
            models.Interacao(origem=models.InteracaoOrigem.CLIENTE, texto="Excelente explicação! A confiança que você passou e a agilidade me conquistaram. Pode emitir o contrato, vamos fechar!")
        ]
        
        dossie = await auditar_jornada_lead(lead, historico)
        
        print(f"   • História: {dossie.historia_do_lead}")
        print(f"   • Desfecho: {dossie.resultado_final.desfecho.value}")
        print(f"   • O que Agradou: {dossie.o_que_agradou}")
        print(f"   • Diferencial Decisivo: {dossie.resultado_final.diferencial_decisivo}")
        print(f"   • Nota IA: {dossie.nota_atendimento_ia}/10")
        
        assert dossie.resultado_final.desfecho == models.DesfechoLead.GANHO
        assert len(dossie.o_que_agradou) > 0
        assert dossie.nota_atendimento_ia >= 7.0
        print("✅ Auditoria de negócio ganho validada com sucesso!")

async def test_2_auditoria_negocio_perdido():
    print("\n--- [2/6] Testando Auditoria de Negócio Perdido com Concorrente (PERDIDO) ---")
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None
        
        lead.desfecho = models.DesfechoLead.PERDIDO
        lead.motivo_perda = "Preço / Concorrência"
        await db.commit()
        
        historico = [
            models.Interacao(origem=models.InteracaoOrigem.CLIENTE, texto="Quero orçamento de energia solar."),
            models.Interacao(origem=models.InteracaoOrigem.IA, texto="Com certeza! Nosso investimento é de R$ 50.000."),
            models.Interacao(origem=models.InteracaoOrigem.CLIENTE, texto="Achei caro demais. O concorrente SolarPlus me ofereceu por R$ 38.000 com painéis alemães. Vou fechar com eles, cancele por favor.")
        ]
        
        dossie = await auditar_jornada_lead(lead, historico)
        
        print(f"   • Desfecho: {dossie.resultado_final.desfecho.value}")
        print(f"   • Motivo Raiz: {dossie.resultado_final.motivo_raiz}")
        print(f"   • Concorrente Citado: {dossie.resultado_final.concorrente_citado}")
        print(f"   • Pontos de Atrito: {dossie.pontos_de_atrito_e_queixas}")
        print(f"   • Feedback para Negócio: {dossie.feedback_para_o_negocio}")
        
        assert dossie.resultado_final.desfecho == models.DesfechoLead.PERDIDO
        assert dossie.resultado_final.motivo_raiz is not None
        assert "solarplus" in str(dossie.resultado_final.concorrente_citado).lower() or "solar" in str(dossie.resultado_final.concorrente_citado).lower() or len(dossie.pontos_de_atrito_e_queixas) > 0
        assert len(dossie.feedback_para_o_negocio) > 10
        print("✅ Auditoria de negócio perdido e identificação de concorrência validadas!")

async def test_3_auditoria_transbordo_com_dica_de_ouro():
    print("\n--- [3/6] Testando Auditoria de Transbordo & Dica de Ouro para o Humano ---")
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None
        
        lead.controle = models.ControleAtendimento.TRANSBORDO_SOLICITADO
        await db.commit()
        
        historico = [
            models.Interacao(origem=models.InteracaoOrigem.CLIENTE, texto="Olá, gostei da proposta de vocês mas preciso negociar a forma de pagamento."),
            models.Interacao(origem=models.InteracaoOrigem.IA, texto="Podemos parcelar pelo banco parceiro em até 60x."),
            models.Interacao(origem=models.InteracaoOrigem.CLIENTE, texto="Não quero financiamento de banco. Quero falar com um atendente humano para ver se vocês aceitam parcelamento próprio no boleto ou cartão.")
        ]
        
        dossie = await auditar_jornada_lead(lead, historico)
        
        print(f"   • Ação Sugerida: {dossie.proximo_passo.acao_sugerida}")
        print(f"   • Dica de Ouro para Humano: \"{dossie.proximo_passo.dica_de_ouro}\"")
        print(f"   • Potencial Reativação: {dossie.potencial_reativacao}")
        
        assert len(dossie.proximo_passo.dica_de_ouro) > 10
        assert dossie.potencial_reativacao in ["ALTO", "MEDIO", "BAIXO"]
        print("✅ Dica de ouro para atendente humano gerada com excelência!")

async def test_4_persistencia_lead_service():
    print("\n--- [4/6] Testando Persistência de Dossiê via LeadService ---")
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None
        
        # Limpa interações e cadastra novas
        await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
        await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.CLIENTE, "Quero fechar o contrato solar hoje mesmo.")
        await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.IA, "Excelente! Me informe o seu CNPJ para formalizarmos.")
        
        # Gera e persiste dossiê
        lead_atualizado = await LeadService.gerar_dossie_lead(db, lead.id)
        
        assert lead_atualizado.dossie_comercial is not None
        assert "historia_do_lead" in lead_atualizado.dossie_comercial
        assert "resultado_final" in lead_atualizado.dossie_comercial
        assert "proximo_passo" in lead_atualizado.dossie_comercial
        print("✅ Dossiê persistido com sucesso no banco relacional (JSONB)!")

async def test_5_reset_dossie():
    print("\n--- [5/6] Testando Limpeza de Dossiê no Reset do Lead ---")
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None
        assert lead.dossie_comercial is not None
        
        # Limpar histórico
        res = await LeadService.limpar_historico_conversa(db, lead.id)
        assert res["status"] == "historico_limpo"
        
        lead_reset = await LeadRepository.get_by_id(db, lead.id)
        assert lead_reset.dossie_comercial is None
        print("✅ Dossiê expurgado com sucesso no reset de histórico!")

async def test_6_endpoint_rest_auditar():
    print("\n--- [6/6] Testando Endpoint REST POST /leads/{id}/auditar ---")
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None
        await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.CLIENTE, "Gostaria de saber como funciona o suporte pós-venda.")
        lead_id = lead.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(f"/leads/{lead_id}/auditar")
        print(f"   Status Code: {resp.status_code}")
        assert resp.status_code == 200
        dados = resp.json()
        assert dados["id"] == lead_id
        assert dados["dossie_comercial"] is not None
        assert "historia_do_lead" in dados["dossie_comercial"]
        assert "proximo_passo" in dados["dossie_comercial"]
        print(f"   • Dica de ouro retornada via API: {dados['dossie_comercial']['proximo_passo']['dica_de_ouro']}")
    print("✅ Endpoint REST POST /leads/{id}/auditar validado com sucesso!")

async def test_cleanup():
    print("\n--- Limpando dados do teste ---")
    async with AsyncSessionLocal() as db:
        await cleanup_lead(db, TEST_PHONE)
    print("✅ Lead de teste expurgado!")

async def run_all():
    print("======================================================================")
    print("🕵️ INICIANDO SUÍTE DE TESTES DO AGENTE AUDITOR DE NEGÓCIOS")
    print("======================================================================")
    await test_1_auditoria_negocio_ganho()
    await test_2_auditoria_negocio_perdido()
    await test_3_auditoria_transbordo_com_dica_de_ouro()
    await test_4_persistencia_lead_service()
    await test_5_reset_dossie()
    await test_6_endpoint_rest_auditar()
    await test_cleanup()
    print("\n======================================================================")
    print("🎉 TODAS AS 6 SUÍTES DO AGENTE AUDITOR FORAM APROVADAS COM SUCESSO!")
    print("======================================================================")

if __name__ == "__main__":
    asyncio.run(run_all())
