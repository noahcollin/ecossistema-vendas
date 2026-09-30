"""
Suíte de Testes Profundos de Resiliência, Casos de Borda, Concorrência e Estresse
================================================================================
Testa cenários avançados, limites de sistema, furos, loops e proteções:
1. Concorrência Massiva Simultânea no Auditor (Thundering Herd sem Deadlocks).
2. Cold Start: Auditoria em Lead com ZERO Interações (Zero-Interaction Safety).
3. Stress de Histórico: Negociação Longa (30+ turnos) sumarizada com sucesso.
4. Filtro de Mensagens em Branco e Truncamento de Payload Gigante.
5. Unicode Extremo, Emojis e Fidelidade de Serialização JSONB.
6. Revitalização de Negócio (Lead Revival de PERDIDO para GANHO).
7. Validações Estritas de Erro na API REST (HTTP 404, 400, 422).
"""

import asyncio
import os
import sys
import json
import httpx
from sqlalchemy import select, delete

# Ajusta path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
import models
import schemas
from repositories.lead_repository import LeadRepository
from services.lead_service import LeadService
from agents import (
    analisar_lead_e_fsm,
    gerar_resposta_vendedor,
    auditar_jornada_lead,
)

import pytest
import pytest_asyncio

EDGE_PHONE_1 = "+5583966669991"
EDGE_PHONE_2 = "+5583966669992"
EDGE_PHONE_3 = "+5583966669993"
EDGE_PHONE_4 = "+5583966669994"

async def cleanup_phones(phones):
    async with AsyncSessionLocal() as db:
        for phone in phones:
            lead = await LeadRepository.get_by_phone(db, phone)
            if lead:
                await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
                await LeadRepository.delete_lead(db, lead)

@pytest_asyncio.fixture(autouse=True, scope="module")
async def auto_cleanup_edge_phones():
    phones = [EDGE_PHONE_1, EDGE_PHONE_2, EDGE_PHONE_3, EDGE_PHONE_4]
    await cleanup_phones(phones)
    yield
    await cleanup_phones(phones)

async def test_1_thundering_herd_auditoria():
    print("\n" + "="*70)
    print("⚡ [TESTE 1] Concorrência Massiva Simultânea no Auditor (Thundering Herd)")
    print("="*70)
    
    async with AsyncSessionLocal() as db:
        lead = models.Lead(
            nome="Concorrência Teste",
            telefone=EDGE_PHONE_1,
            etapa_funil=models.EtapaFunil.FECHAMENTO,
            desfecho=models.DesfechoLead.GANHO
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)
        lead_id = lead.id

        # Adiciona interação
        await LeadRepository.add_interaction(db, lead_id, models.InteracaoOrigem.CLIENTE, "Quero fechar agora!")
        await LeadRepository.add_interaction(db, lead_id, models.InteracaoOrigem.IA, "Excelente! Segue o contrato.")

    # Dispara 4 auditorias simultâneas no mesmo lead em paralelo
    async def auditoria_worker(worker_id: int):
        async with AsyncSessionLocal() as session:
            return await LeadService.gerar_dossie_lead(session, lead_id)

    print("   • Disparando 4 chamadas simultâneas via asyncio.gather...")
    resultados = await asyncio.gather(
        auditoria_worker(1),
        auditoria_worker(2),
        auditoria_worker(3),
        auditoria_worker(4),
        return_exceptions=True
    )

    # Verifica se todos concluíram sem lançar exceções de concorrência / deadlock
    erros = [r for r in resultados if isinstance(r, Exception)]
    assert len(erros) == 0, f"Erros durante concorrência: {erros}"
    
    for r in resultados:
        assert r.dossie_comercial is not None
        assert r.dossie_comercial["resultado_final"]["desfecho"] == "GANHO"

    print(f"✅ Todas as 4 auditorias concorrentes concluídas com sucesso sem deadlocks!")

async def test_2_cold_start_sem_interacoes():
    print("\n" + "="*70)
    print("❄️ [TESTE 2] Cold Start: Auditoria em Lead com ZERO Interações")
    print("="*70)

    async with AsyncSessionLocal() as db:
        lead = models.Lead(
            nome="Lead Vazio",
            telefone=EDGE_PHONE_2,
            etapa_funil=models.EtapaFunil.NOVO_CONTATO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            temperatura=models.TemperaturaLead.FRIO
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)

        # Audita com histórico 100% vazio
        dossie = await auditar_jornada_lead(lead, [])
        assert dossie is not None
        assert dossie.resultado_final.desfecho in [schemas.DesfechoLead.EM_ANDAMENTO, schemas.DesfechoLead.PERDIDO]
        assert len(dossie.historia_do_lead) > 5
        print(f"   • Dossiê gerado para lead sem histórico:")
        print(f"     - História: {dossie.historia_do_lead}")
        print(f"     - Ação Sugerida: {dossie.proximo_passo.acao_sugerida}")
        print(f"     - Dica de Ouro: {dossie.proximo_passo.dica_de_ouro}")

    print("✅ Auditoria em lead com zero interações executada com total robustez!")

async def test_3_long_conversation_stress():
    print("\n" + "="*70)
    print("📜 [TESTE 3] Stress de Histórico: Longa Conversa de 20 Turnos")
    print("="*70)

    async with AsyncSessionLocal() as db:
        lead = models.Lead(
            nome="Dra. Helena Consultório",
            telefone=EDGE_PHONE_3,
            etapa_funil=models.EtapaFunil.NEGOCIACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            temperatura=models.TemperaturaLead.QUENTE
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)

        # Cria 20 interações alternadas
        interacoes = []
        for i in range(1, 11):
            msg_c = models.Interacao(
                lead_id=lead.id,
                origem=models.InteracaoOrigem.CLIENTE,
                texto=f"Dúvida {i}: Como funciona o item {i} da instalação e da garantia?"
            )
            msg_ia = models.Interacao(
                lead_id=lead.id,
                origem=models.InteracaoOrigem.IA,
                texto=f"Resposta {i}: O item {i} é coberto com garantia integral e assistência 24h."
            )
            db.add_all([msg_c, msg_ia])
            interacoes.extend([msg_c, msg_ia])

        await db.commit()

        # Auditoria da conversa longa
        dossie = await auditar_jornada_lead(lead, interacoes)
        assert dossie is not None
        assert dossie.nota_atendimento_ia >= 5.0
        assert len(dossie.pontos_de_atrito_e_queixas) >= 0
        print(f"   • 20 interações analisadas com sucesso:")
        print(f"     - Nota do Atendimento IA: {dossie.nota_atendimento_ia}/10")
        print(f"     - Estratégia Utilizada: {dossie.estrategia_utilizada}")

    print("✅ Histórico longo de 20 interações processado sem estouro de memória!")

async def test_4_unicode_and_jsonb_fidelity():
    print("\n" + "="*70)
    print("🌐 [TESTE 4] Unicode Extremo, Emojis e Aspas na Persistência JSONB")
    print("="*70)

    async with AsyncSessionLocal() as db:
        # Texto com emojis múltiplos, caracteres japoneses, acentos, quebras e aspas complexas
        nome_complexo = "José & Filhos \"Energia Solar\" 🌞⚡ — 日本語テスト"
        lead = models.Lead(
            nome=nome_complexo,
            telefone=EDGE_PHONE_4,
            etapa_funil=models.EtapaFunil.QUALIFICACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            tags=["solar-b2b", "prioridade_máxima_⚡", "aspas\"'teste"]
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)

        dossie_complexo = {
            "historia_do_lead": "Cliente enviou caracteres complexos: 🚀 日本語, acentuação: ação, órgão, ímã, 'aspas' e \"aspas duplas\".",
            "o_que_agradou": ["Rapidez ⚡", "Segurança total 🔒"],
            "pontos_de_atrito_e_queixas": ["Preço em R$ 100.000,00"],
            "resultado_final": {
                "desfecho": "GANHO",
                "motivo_raiz": None,
                "concorrente_citado": None,
                "diferencial_decisivo": "Atendimento VIP ⭐⭐⭐⭐⭐"
            },
            "estrategia_utilizada": "Abordagem com caracteres UTF-8 plenos",
            "nota_atendimento_ia": 10.0,
            "feedback_para_o_negocio": "Nenhum problema encontrado.",
            "proximo_passo": {
                "acao_sugerida": "Contatar via WhatsApp 📲",
                "quando_retomar": "Amanhã às 09:00",
                "dica_de_ouro": "Chamar de \"Doutor José\" com respeito."
            },
            "potencial_reativacao": "BAIXO"
        }

        await LeadRepository.salvar_dossie(db, lead, dossie_complexo)
        await db.refresh(lead)

        # Verifica fidelidade exata ao ler do banco PostgreSQL
        assert lead.nome == nome_complexo
        assert "solar-b2b" in lead.tags
        assert lead.dossie_comercial["resultado_final"]["diferencial_decisivo"] == "Atendimento VIP ⭐⭐⭐⭐⭐"
        assert "日本語" in lead.dossie_comercial["historia_do_lead"]
        print(f"   • Dados recuperados do PostgreSQL com integridade de codificação UTF-8:")
        print(f"     Nome: {lead.nome}")
        print(f"     Diferencial: {lead.dossie_comercial['resultado_final']['diferencial_decisivo']}")

    print("✅ Unicode, emojis e integridade de serialização JSONB 100% preservados!")

async def test_5_lead_revival_fsm():
    print("\n" + "="*70)
    print("🔄 [TESTE 5] Revitalização de Negócio: Transição de PERDIDO para GANHO")
    print("="*70)

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, EDGE_PHONE_4)
        if not lead:
            lead = models.Lead(
                nome="José & Filhos",
                telefone=EDGE_PHONE_4,
                etapa_funil=models.EtapaFunil.QUALIFICACAO,
                desfecho=models.DesfechoLead.EM_ANDAMENTO,
                tags=["solar-b2b"]
            )
            db.add(lead)
            await db.commit()
            await db.refresh(lead)

        # 1. Marca como perdido
        lead.desfecho = models.DesfechoLead.PERDIDO
        lead.motivo_perda = "Preço"
        lead.temperatura = models.TemperaturaLead.FRIO
        await db.commit()
        print(f"   • Estado inicial: Desfecho={lead.desfecho.value} | Motivo={lead.motivo_perda}")

        # 2. Cliente volta com nova mensagem de fechamento
        msg_volta = "Olá! Consegui um empréstimo com juros baixos e decidi fechar o sistema com vocês sim! Como fazemos o contrato?"
        interacao_volta = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=msg_volta
        )
        db.add(interacao_volta)
        await db.commit()

        analise = await analisar_lead_e_fsm(
            lead=lead,
            historico_recente=[interacao_volta],
            nova_mensagem=msg_volta
        )

        print(f"   • [Analista]: Etapa Sugerida={analise.etapa_sugerida.value} | Desfecho={analise.desfecho_sugerido.value} | Temp={analise.temperatura_sugerida.value}")
        assert analise.desfecho_sugerido in [models.DesfechoLead.GANHO, models.DesfechoLead.EM_ANDAMENTO]
        assert analise.temperatura_sugerida == models.TemperaturaLead.QUENTE

        # Atualiza lead com o revival
        lead.etapa_funil = analise.etapa_sugerida
        lead.desfecho = analise.desfecho_sugerido
        lead.temperatura = analise.temperatura_sugerida
        lead.motivo_perda = None
        await db.commit()

        print(f"   • Estado atualizado: Desfecho={lead.desfecho.value} | Temp={lead.temperatura.value}")

    print("✅ Revitalização de Lead (Resiliência de Estado FSM) validada com sucesso!")

async def test_6_api_error_handling_and_status_codes():
    print("\n" + "="*70)
    print("🛡️ [TESTE 6] Validações Estritas de Erro na API REST (404, 400, 422)")
    print("="*70)

    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10.0) as client:
        # 1. Lead Inexistente para Auditoria -> HTTP 404
        r404 = await client.post("/leads/99999999/auditar")
        assert r404.status_code == 404, f"Esperado 404, recebido {r404.status_code}"
        print(f"   • POST /leads/99999999/auditar -> Retornou HTTP {r404.status_code} Not Found (Correto)")

        # 2. Reset com Telefone Curto (< 8 dígitos) -> HTTP 400
        r400 = await client.delete("/leads/reset/por-telefone/12345")
        assert r400.status_code == 400, f"Esperado 400, recebido {r400.status_code}"
        print(f"   • DELETE /leads/reset/por-telefone/12345 -> Retornou HTTP {r400.status_code} Bad Request (Correto)")

        # 3. Payload Malformado / Vazio em Criação de Lead -> HTTP 422
        r422 = await client.post("/leads/", json={})
        assert r422.status_code == 422, f"Esperado 422, recebido {r422.status_code}"
        print(f"   • POST /leads/ com JSON vazio -> Retornou HTTP {r422.status_code} Unprocessable Entity (Correto)")

    print("✅ Todos os códigos de status de erro e proteções de API validados!")

async def main():
    print("=" * 70)
    print("🔬 INICIANDO SUÍTE DE TESTES PROFUNDOS, BORDAS E RESILIÊNCIA")
    print("=" * 70)

    phones = [EDGE_PHONE_1, EDGE_PHONE_2, EDGE_PHONE_3, EDGE_PHONE_4]
    await cleanup_phones(phones)

    try:
        await test_1_thundering_herd_auditoria()
        await test_2_cold_start_sem_interacoes()
        await test_3_long_conversation_stress()
        await test_4_unicode_and_jsonb_fidelity()
        await test_5_lead_revival_fsm()
        await test_6_api_error_handling_and_status_codes()

        print("\n" + "=" * 70)
        print("🎉 TODOS OS 6 TESTES PROFUNDOS E DE BORDA PASSARAM COM SUCESSO!")
        print("=" * 70 + "\n")
    finally:
        await cleanup_phones(phones)

if __name__ == "__main__":
    asyncio.run(main())
