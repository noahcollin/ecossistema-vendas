"""
Bateria de Testes Abrangente das Novas Funcionalidades e Alterações
===================================================================
Valida de ponta a ponta:
1. Camada de Dados, 4 Dimensões e Dossiê Comercial JSONB.
2. Integridade e Desacoplamento dos 2 Arquivos de Prompts (agents vs media).
3. Ciclo de Negociação Multi-Agente (Vendedor -> Analista -> Auditor).
4. Transbordo Humano, Silenciamento da IA e Dica de Ouro.
5. Perda com Concorrência e Feedback Estratégico para o Negócio.
6. Endpoint REST POST /leads/{id}/auditar e Reset Completo de Memória.
"""

import asyncio
import os
import sys

# Ajusta path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import httpx
from sqlalchemy import select, delete
from core.database import AsyncSessionLocal
import models
import schemas
from repositories.lead_repository import LeadRepository
from services.lead_service import LeadService
from services.agents import (
    analisar_lead_e_fsm,
    gerar_resposta_vendedor,
    auditar_jornada_lead,
    PROMPT_BASE_VENDEDOR,
    ORIENTACOES_POR_ESTAGIO,
    PROMPT_SISTEMA_ANALISTA,
    PROMPT_SISTEMA_AUDITOR,
)
from services.media.prompts import (
    PROMPT_OLHOS_DO_VENDEDOR,
    PROMPT_GIF,
    PROMPT_RESUMO_PDF,
)

TEST_PHONE = "+5583977770001"

async def cleanup(db, telefone: str):
    lead = await LeadRepository.get_by_phone(db, telefone)
    if lead:
        await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
        await LeadRepository.delete_lead(db, lead)

async def test_1_prompts_separation():
    print("\n--- [1/6] Testando Integridade e Separação dos 2 Arquivos de Prompts ---")
    
    # 1. Prompts de Agentes Comerciais
    assert PROMPT_BASE_VENDEDOR is not None and "Seu Zé" in PROMPT_BASE_VENDEDOR
    assert models.EtapaFunil.QUALIFICACAO in ORIENTACOES_POR_ESTAGIO
    assert models.EtapaFunil.FECHAMENTO in ORIENTACOES_POR_ESTAGIO
    assert "4 DIMENSÕES" in PROMPT_SISTEMA_ANALISTA
    assert "Auditor de Negócios" in PROMPT_SISTEMA_AUDITOR or "DOSSIÊ" in PROMPT_SISTEMA_AUDITOR
    print("   • Arquivo services/agents/prompts.py: Vendedor, Estágios, Analista FSM e Auditor validados.")

    # 2. Prompts de Mídia / Visão Computacional
    assert PROMPT_OLHOS_DO_VENDEDOR is not None and "visão computacional" in PROMPT_OLHOS_DO_VENDEDOR
    assert PROMPT_GIF is not None and "GIF" in PROMPT_GIF
    assert PROMPT_RESUMO_PDF is not None and "PDF" in PROMPT_RESUMO_PDF
    print("   • Arquivo services/media/prompts.py: Visão, GIF/Meme e PDF validados.")

    print("✅ Separação de responsabilidades dos prompts validada com sucesso!")

async def test_2_model_and_jsonb_dossie():
    print("\n--- [2/6] Testando Modelo ORM, 4 Dimensões e Dossiê Comercial JSONB ---")
    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_PHONE)
        
        lead = models.Lead(
            nome="Amanda Silva",
            telefone=TEST_PHONE,
            etapa_funil=models.EtapaFunil.NOVO_CONTATO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.PILOTO_IA,
            temperatura=models.TemperaturaLead.MORNO,
            valor_estimado=15000.0,
            tags=["solar", "residencial"]
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)

        assert lead.etapa_funil == models.EtapaFunil.NOVO_CONTATO
        assert lead.desfecho == models.DesfechoLead.EM_ANDAMENTO
        assert lead.controle == models.ControleAtendimento.PILOTO_IA
        assert lead.temperatura == models.TemperaturaLead.MORNO
        assert lead.dossie_comercial is None

        # Salva dossiê mock
        mock_dossie = {
            "historia_do_lead": "Amanda buscou informações para sua casa.",
            "o_que_agradou": ["Atendimento rápido"],
            "pontos_de_atrito_e_queixas": [],
            "resultado_final": {
                "desfecho": "GANHO",
                "motivo_raiz": "Economia comprovada",
                "concorrente_citado": None,
                "diferencial_decisivo": "Qualidade técnica"
            },
            "estrategia_utilizada": "Abordagem consultiva residencial",
            "nota_atendimento_ia": 10.0,
            "feedback_para_o_negocio": "Lead com perfil ideal",
            "proximo_passo": {
                "acao_recomendada": "Assinar contrato",
                "dica_de_ouro": "Reforçar garantia de instalação",
                "potencial_reativacao": "BAIXO"
            }
        }
        await LeadRepository.salvar_dossie(db, lead, mock_dossie)
        await db.refresh(lead)

        assert lead.dossie_comercial is not None
        assert lead.dossie_comercial["resultado_final"]["desfecho"] == "GANHO"
        assert lead.dossie_comercial["nota_atendimento_ia"] == 10.0
        print(f"   • Dossiê JSONB persistido no PostgreSQL: {lead.dossie_comercial['resultado_final']['desfecho']}")
        print("✅ Persistência das 4 dimensões e Dossiê JSONB validada com sucesso!")

async def test_3_multi_agent_flow():
    print("\n--- [3/6] Testando Ciclo Completo Multi-Agente (Vendedor -> Analista -> Auditor) ---")
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None

        msg_cliente = "Oi Seu Zé! Quero colocar painel solar no meu sítio. A conta lá dá uns R$ 1.800 por mês. Pode me ajudar?"
        interacao_cliente = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=msg_cliente
        )
        db.add(interacao_cliente)
        await db.commit()

        # 1. Analista avalia necessidade
        analise = await analisar_lead_e_fsm(lead=lead, historico_recente=[interacao_cliente], nova_mensagem=msg_cliente)
        lead.resumo_perfil = analise.resumo_perfil
        lead.dados_qualificacao = analise.dados_qualificacao.model_dump()
        lead.etapa_funil = analise.etapa_sugerida
        lead.desfecho = analise.desfecho_sugerido
        lead.temperatura = analise.temperatura_sugerida
        await db.commit()

        print(f"   • [Analista]: Etapa={lead.etapa_funil.value} | Desfecho={lead.desfecho.value} | Temp={lead.temperatura.value}")
        assert lead.etapa_funil in [models.EtapaFunil.QUALIFICACAO, models.EtapaFunil.NEGOCIACAO]

        # 2. Vendedor responde
        resp_vendedor = await gerar_resposta_vendedor(
            nome_cliente_bruto=lead.nome,
            ficha_resumo=lead.resumo_perfil,
            etapa_funil=lead.etapa_funil,
            historico_recente=[interacao_cliente]
        )
        print(f"   • [Seu Zé]: \"{resp_vendedor}\"")
        assert len(resp_vendedor) > 20

        interacao_ia = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.IA,
            texto=resp_vendedor
        )
        db.add(interacao_ia)
        await db.commit()

        # 3. Cliente aceita e fecha
        msg_fechamento = "Fechado então! Adorei a proposta, pode emitir o contrato no meu nome."
        interacao_fechamento = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=msg_fechamento
        )
        db.add(interacao_fechamento)
        await db.commit()

        # Atualiza para ganho
        lead.etapa_funil = models.EtapaFunil.FECHAMENTO
        lead.desfecho = models.DesfechoLead.GANHO
        lead.temperatura = models.TemperaturaLead.QUENTE
        await db.commit()

        # 4. Auditor avalia a jornada completa
        historico_total = [interacao_cliente, interacao_ia, interacao_fechamento]
        dossie = await auditar_jornada_lead(lead, historico_total)
        assert dossie.resultado_final.desfecho in [schemas.DesfechoLead.GANHO, schemas.DesfechoLead.EM_ANDAMENTO]
        assert len(dossie.o_que_agradou) > 0
        assert dossie.nota_atendimento_ia >= 7.0
        print(f"   • [Auditor Executivo]: Desfecho={dossie.resultado_final.desfecho.value} | Nota IA={dossie.nota_atendimento_ia}/10")
        print(f"   • Dica de ouro gerada: \"{dossie.proximo_passo.dica_de_ouro}\"")
        print("✅ Ciclo Multi-Agente (Vendedor -> Analista -> Auditor) validado com sucesso!")

async def test_4_transbordo_and_human_golden_tip():
    print("\n--- [4/6] Testando Transbordo Humano, Silenciamento da IA e Dica de Ouro ---")
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None

        # Cliente pede humano
        msg_transbordo = "Não quero falar com robô. Quero uma pessoa de verdade para tirar uma dúvida sobre financiamento bancário agora!"
        interacao_transbordo = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=msg_transbordo
        )
        db.add(interacao_transbordo)
        await db.commit()

        analise = await analisar_lead_e_fsm(lead=lead, historico_recente=[interacao_transbordo], nova_mensagem=msg_transbordo)
        assert analise.transbordo_sugerido is True
        
        # Altera controle para humano
        lead.controle = models.ControleAtendimento.TRANSBORDO_SOLICITADO
        await db.commit()

        print(f"   • [Analista]: Transbordo detectado={analise.transbordo_sugerido} | Controle={lead.controle.value}")

        # Gera dossiê com dica para o atendente
        dossie = await auditar_jornada_lead(lead, [interacao_transbordo])
        assert dossie.proximo_passo.dica_de_ouro is not None
        assert len(dossie.proximo_passo.dica_de_ouro) > 10
        print(f"   • Dica de ouro para atendente humano: \"{dossie.proximo_passo.dica_de_ouro}\"")
        print("✅ Transbordo Humano e Dica de Ouro validados com sucesso!")

async def test_5_loss_and_competitor_analysis():
    print("\n--- [5/6] Testando Perda, Concorrência e Feedback Estratégico ---")
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None

        msg_perda = "Obrigado, mas a empresa concorrente SunPower fez um orçamento 30% mais barato e vou fechar com eles. Cancelem o atendimento."
        interacao_perda = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=msg_perda
        )
        db.add(interacao_perda)
        await db.commit()

        analise = await analisar_lead_e_fsm(lead=lead, historico_recente=[interacao_perda], nova_mensagem=msg_perda)
        lead.desfecho = analise.desfecho_sugerido
        lead.motivo_perda = analise.motivo_perda
        await db.commit()

        print(f"   • [Analista]: Desfecho={lead.desfecho.value} | Motivo={lead.motivo_perda}")
        assert lead.desfecho == models.DesfechoLead.PERDIDO
        assert lead.motivo_perda is not None

        dossie = await auditar_jornada_lead(lead, [interacao_perda])
        assert dossie.resultado_final.desfecho == schemas.DesfechoLead.PERDIDO
        assert dossie.resultado_final.concorrente_citado is not None and "SunPower" in dossie.resultado_final.concorrente_citado
        assert len(dossie.feedback_para_o_negocio) > 10
        print(f"   • [Auditor]: Concorrente identificado: \"{dossie.resultado_final.concorrente_citado}\"")
        print(f"   • Feedback para o Negócio: \"{dossie.feedback_para_o_negocio}\"")
        print("✅ Detecção de perda, concorrência e feedback estratégico validados!")

async def test_6_api_endpoint_and_full_reset():
    print("\n--- [6/6] Testando Endpoint REST POST /leads/{id}/auditar e Reset Completo ---")
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TEST_PHONE)
        assert lead is not None
        lead_id = lead.id

    # 1. Chamada REST ao endpoint de auditoria
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30.0) as client:
        resp = await client.post(f"/leads/{lead_id}/auditar")
        assert resp.status_code == 200, f"Falha na API: {resp.text}"
        data = resp.json()
        assert "dossie_comercial" in data and data["dossie_comercial"] is not None
        assert "historia_do_lead" in data["dossie_comercial"]
        print(f"   • Endpoint REST POST /leads/{lead_id}/auditar: HTTP 200 OK")
        print(f"   • Dossiê retornado com sucesso via API!")

    # 2. Teste de Reset Completo via LeadService
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_id(db, lead_id)
        assert lead.dossie_comercial is not None

        await LeadService.limpar_historico_conversa(db, lead.id)
        await db.refresh(lead)

        assert lead.resumo_perfil is None
        assert lead.dados_qualificacao is None
        assert lead.dossie_comercial is None
        assert lead.etapa_funil == models.EtapaFunil.NOVO_CONTATO
        assert lead.desfecho == models.DesfechoLead.EM_ANDAMENTO
        assert lead.controle == models.ControleAtendimento.PILOTO_IA
        assert lead.temperatura == models.TemperaturaLead.FRIO
        print("   • LeadService.limpar_historico_conversa restaurou as 4 dimensões e expurgou o dossiê!")

        # Cleanup final
        await cleanup(db, TEST_PHONE)
        print("   • Cleanup do lead de testes concluído.")

    print("✅ Endpoint REST e Reset Completo validados com 100% de sucesso!")

async def main():
    print("=" * 70)
    print("🧪 INICIANDO BATERIA DE TESTES DAS ALTERAÇÕES E ADIÇÕES")
    print("=" * 70)

    await test_1_prompts_separation()
    await test_2_model_and_jsonb_dossie()
    await test_3_multi_agent_flow()
    await test_4_transbordo_and_human_golden_tip()
    await test_5_loss_and_competitor_analysis()
    await test_6_api_endpoint_and_full_reset()

    print("\n" + "=" * 70)
    print("🎉 TODAS AS 6 SUÍTES DA BATERIA DE TESTES FORAM APROVADAS!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
