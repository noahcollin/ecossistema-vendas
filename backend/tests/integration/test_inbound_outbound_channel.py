"""
Suíte de Testes: Tipos de Entrada (Inbound vs Outbound) e Canais de Origem
==========================================================================
Valida:
1. Detecção automática de META_ADS (Instagram / Facebook).
2. Detecção automática de INDICACAO.
3. Detecção automática de SITE_LANDING_PAGE.
4. Criação e persistência de lead OUTBOUND via API / Service.
5. Inclusão de tipo_entrada e origem_canal no Dossiê Comercial Executivo.
"""

import asyncio
import os
import sys
import httpx

# Ajusta path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
import models
import schemas
from repositories.lead_repository import LeadRepository
from services.lead_service import LeadService
from agents import (
    analisar_lead_e_fsm,
    auditar_jornada_lead,
)

PHONE_META = "+5583955550001"
PHONE_INDICACAO = "+5583955550002"
PHONE_SITE = "+5583955550003"
PHONE_OUTBOUND = "+5583955550004"

async def cleanup(phones):
    async with AsyncSessionLocal() as db:
        for phone in phones:
            lead = await LeadRepository.get_by_phone(db, phone)
            if lead:
                await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
                await LeadRepository.delete_lead(db, lead)

async def test_1_meta_ads_detection():
    print("\n" + "="*70)
    print("📱 [TESTE 1] Detecção Automática de Meta Ads (Instagram/Facebook)")
    print("="*70)

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.create(
            db=db,
            telefone=PHONE_META,
            nome="Juliana Anúncio",
            tipo_entrada=models.TipoEntradaLead.INBOUND,
            origem_canal="WHATSAPP_DIRETO"
        )
        msg_meta = "Olá! Vi o anúncio no Instagram sobre redução de 90% na conta de luz e gostaria de uma simulação para o meu comércio."
        interacao = await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.CLIENTE, msg_meta)

        analise = await analisar_lead_e_fsm(lead=lead, historico_recente=[interacao], nova_mensagem=msg_meta)
        print(f"   • Mensagem do cliente: \"{msg_meta}\"")
        print(f"   • Canal detectado pela IA: {analise.origem_canal_detectada}")
        assert analise.origem_canal_detectada == "META_ADS"

        # Atualiza canal
        lead.origem_canal = analise.origem_canal_detectada
        await db.commit()
        await db.refresh(lead)

        assert lead.tipo_entrada == models.TipoEntradaLead.INBOUND
        assert lead.origem_canal == "META_ADS"

    print("✅ Origem META_ADS detectada e persistida com sucesso!")

async def test_2_indicacao_detection():
    print("\n" + "="*70)
    print("🤝 [TESTE 2] Detecção Automática de Indicação")
    print("="*70)

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.create(
            db=db,
            telefone=PHONE_INDICACAO,
            nome="Rodrigo Amigo",
            tipo_entrada=models.TipoEntradaLead.INBOUND,
            origem_canal="WHATSAPP_DIRETO"
        )
        msg_ind = "Boa tarde! O Dr. Paulo me indicou a Inteligentte para ver se compensa colocar energia solar na minha clínica."
        interacao = await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.CLIENTE, msg_ind)

        analise = await analisar_lead_e_fsm(lead=lead, historico_recente=[interacao], nova_mensagem=msg_ind)
        print(f"   • Mensagem do cliente: \"{msg_ind}\"")
        print(f"   • Canal detectado pela IA: {analise.origem_canal_detectada}")
        assert analise.origem_canal_detectada == "INDICACAO"

        lead.origem_canal = analise.origem_canal_detectada
        await db.commit()
        await db.refresh(lead)

        assert lead.origem_canal == "INDICACAO"

    print("✅ Origem INDICACAO detectada e persistida com sucesso!")

async def test_3_site_landing_page_detection():
    print("\n" + "="*70)
    print("💻 [TESTE 3] Detecção Automática de Site / Landing Page")
    print("="*70)

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.create(
            db=db,
            telefone=PHONE_SITE,
            nome="Fernando Web",
            tipo_entrada=models.TipoEntradaLead.INBOUND,
            origem_canal="WHATSAPP_DIRETO"
        )
        msg_site = "Olá! Vim pelo botão do site oficial de vocês e gostaria de mais detalhes sobre o parcelamento."
        interacao = await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.CLIENTE, msg_site)

        analise = await analisar_lead_e_fsm(lead=lead, historico_recente=[interacao], nova_mensagem=msg_site)
        print(f"   • Mensagem do cliente: \"{msg_site}\"")
        print(f"   • Canal detectado pela IA: {analise.origem_canal_detectada}")
        assert analise.origem_canal_detectada in ["SITE_LANDING_PAGE", "SITE"]

        lead.origem_canal = analise.origem_canal_detectada
        await db.commit()
        await db.refresh(lead)

        assert lead.origem_canal in ["SITE_LANDING_PAGE", "SITE"]

    print("✅ Origem SITE_LANDING_PAGE detectada com sucesso!")

async def test_4_outbound_manual_creation():
    print("\n" + "="*70)
    print("📤 [TESTE 4] Criação Manual de Lead OUTBOUND via REST / Service")
    print("="*70)

    lead_in = schemas.LeadCreate(
        nome="Indústria Metalmecânica Vale",
        telefone=PHONE_OUTBOUND,
        tipo_entrada=schemas.TipoEntradaLead.OUTBOUND,
        origem_canal="LISTA_PROSPECCAO_B2B",
        etapa_funil=models.EtapaFunil.QUALIFICACAO,
        valor_estimado=85000.0
    )

    async with AsyncSessionLocal() as db:
        lead = await LeadService.criar_lead(db, lead_in)
        assert lead.id is not None
        assert lead.tipo_entrada == models.TipoEntradaLead.OUTBOUND
        assert lead.origem_canal == "LISTA_PROSPECCAO_B2B"
        assert lead.valor_estimado == 85000.0

        print(f"   • Lead Outbound persistido:")
        print(f"     - Nome: {lead.nome}")
        print(f"     - Tipo de Entrada: {lead.tipo_entrada.value}")
        print(f"     - Origem Canal: {lead.origem_canal}")

    # Valida recuperação via API REST
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10.0) as client:
        resp = await client.get("/leads/")
        assert resp.status_code == 200
        leads_json = resp.json()
        lead_api = next((l for l in leads_json if l["telefone"] == PHONE_OUTBOUND), None)
        assert lead_api is not None
        assert lead_api["tipo_entrada"] == "OUTBOUND"
        assert lead_api["origem_canal"] == "LISTA_PROSPECCAO_B2B"
        print(f"   • Validação na API REST GET /leads/: Retornou tipo_entrada e origem_canal perfeitamente!")

    print("✅ Cadastro e leitura de Lead OUTBOUND validados com 100% de sucesso!")

async def test_5_dossie_comercial_com_aquisicao():
    print("\n" + "="*70)
    print("📋 [TESTE 5] Presença de Inbound/Outbound e Canal no Dossiê Comercial")
    print("="*70)

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, PHONE_META)
        assert lead is not None

        # Adiciona mensagem de fechamento
        int_fecha = await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.CLIENTE, "Quero fechar sim, pode emitir!")
        lead.desfecho = models.DesfechoLead.GANHO
        await db.commit()

        dossie = await auditar_jornada_lead(lead, [int_fecha])
        assert dossie is not None
        assert dossie.tipo_entrada == "INBOUND"
        assert dossie.origem_canal == "META_ADS"

        print(f"   • Dossiê Executivo gerado com dados de aquisição:")
        print(f"     - Tipo de Entrada: {dossie.tipo_entrada}")
        print(f"     - Canal de Origem: {dossie.origem_canal}")
        print(f"     - Desfecho: {dossie.resultado_final.desfecho.value}")
        print(f"     - Dica de Ouro: \"{dossie.proximo_passo.dica_de_ouro}\"")

    print("✅ Dossiê Comercial reflete canal de aquisição com precisão!")

async def main():
    print("=" * 70)
    print("🧪 INICIANDO SUÍTE DE TESTES: INBOUND/OUTBOUND & CANAIS DE ORIGEM")
    print("=" * 70)

    phones = [PHONE_META, PHONE_INDICACAO, PHONE_SITE, PHONE_OUTBOUND]
    await cleanup(phones)

    try:
        await test_1_meta_ads_detection()
        await test_2_indicacao_detection()
        await test_3_site_landing_page_detection()
        await test_4_outbound_manual_creation()
        await test_5_dossie_comercial_com_aquisicao()

        print("\n" + "=" * 70)
        print("🎉 TODOS OS 5 TESTES DE INBOUND/OUTBOUND E CANAIS FORAM APROVADOS!")
        print("=" * 70 + "\n")
    finally:
        await cleanup(phones)

if __name__ == "__main__":
    asyncio.run(main())
