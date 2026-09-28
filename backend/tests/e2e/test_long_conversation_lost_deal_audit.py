"""
SIMULAÇÃO DE LONGA CONVERSA COM LEAD PERDIDO & AUDITORIA COMERCIAL EXECUTIVA
=============================================================================
Cenário: Dr. Eduardo (Clínica em João Pessoa)
1. Entrada Inbound via Google Search (GOOGLE_SEARCH).
2. Diálogo longo de qualificação clínica (ar-condicionados, R$ 5.200/mês).
3. Avanço para Negociação.
4. Entrada de Concorrente Agressivo ("Sol Forte Engenharia") com preço 20% menor e parcelamento em boleto.
5. Vendedor tenta contornar por qualidade/garantia, mas cliente opta pelo concorrente por fluxo de caixa.
6. FSM preserva ortogonalmente: etapa_funil = NEGOCIACAO, desfecho = PERDIDO, motivo_perda = "Preço / Concorrência Sol Forte".
7. DealAuditorAgent gera o Dossiê Comercial Executivo em JSONB com análise de concorrência, feedback e dica de ouro para repescagem.
"""

import asyncio
import os
import sys
import json
import time

# Ajusta path para o root do backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
from core.config import settings
import models
import schemas
from repositories.lead_repository import LeadRepository
from agents import (
    analisar_lead_e_fsm,
    gerar_resposta_vendedor,
    auditar_jornada_lead
)

TEST_PHONE = "+5583994440008"

ROTEIRO_PERDA = [
    {
        "turno": 1,
        "fase": "NOVO_CONTATO",
        "msg_cliente": (
            "Olá, boa tarde! Sou o Dr. Eduardo, diretor da Clínica Bem Estar aqui no bairro de Manaíra em João Pessoa. "
            "Encontrei vocês através de uma pesquisa no Google sobre energia solar para clínicas e empresas."
        )
    },
    {
        "turno": 2,
        "fase": "QUALIFICACAO",
        "msg_cliente": (
            "Nossa clínica possui 8 consultórios com ar-condicionado ligado o dia todo e equipamentos de ultrassom. "
            "A conta de energia da Energisa vem em média R$ 5.200 por mês. Queremos avaliar a viabilidade de instalar placas no nosso prédio próprio."
        )
    },
    {
        "turno": 3,
        "fase": "QUALIFICACAO",
        "msg_cliente": (
            "O prédio tem laje ampla impermeabilizada e sol pleno o dia todo. "
            "Vocês conseguem me passar uma estimativa de quanto precisaríamos investir e o tempo de retorno desse investimento?"
        )
    },
    {
        "turno": 4,
        "fase": "NEGOCIACAO",
        "msg_cliente": (
            "Recebi a proposta estimada de vocês em torno de R$ 95.000 com os inversores industriais. "
            "O projeto parece bem robusto, mas nosso conselho de sócios estipulou um teto de investimento menor para este trimestre."
        )
    },
    {
        "turno": 5,
        "fase": "NEGOCIACAO",
        "msg_cliente": (
            "Para ser bem franco com você, Seu Zé: a empresa concorrente Sol Forte Engenharia veio aqui na clínica ontem, "
            "analisou a nossa laje e nos entregou uma proposta de R$ 76.000, cobrindo o valor e oferecendo parcelamento direto no boleto em 24x sem juros. "
            "A Inteligentte consegue cobrir essa condição ou flexibilizar o pagamento?"
        )
    },
    {
        "turno": 6,
        "fase": "NEGOCIACAO",
        "msg_cliente": (
            "Entendo perfeitamente o seu ponto sobre os inversores premium de vocês e os 10 anos de garantia técnica. "
            "Porém, R$ 19.000 de diferença à vista pesa muito para nossa diretoria financeira no momento atual."
        )
    },
    {
        "turno": 7,
        "fase": "PERDIDO",
        "msg_cliente": (
            "Seu Zé, acabei de sair da reunião com os outros sócios da clínica e decidimos fechar com a Sol Forte Engenharia mesmo, "
            "principalmente pela condição de boleto parcelado sem juros deles. "
            "Agradeço imensamente sua atenção e a educação no atendimento, mas por hora vamos cancelar o projeto com vocês. Um abraço!"
        )
    }
]

async def cleanup(db, telefone: str):
    lead = await LeadRepository.get_by_phone(db, telefone)
    if lead:
        await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
        await LeadRepository.delete_lead(db, lead)

async def executar_simulacao_perda():
    print("=" * 80)
    print("📉 SIMULAÇÃO DE JORNADA LONGA: LEAD PERDIDO PARA CONCORRÊNCIA (SOL FORTE)")
    print("=" * 80)

    settings.DYNAMIC_MODEL_ROUTING = True
    settings.MODEL_CLOSER_FAST = "gpt-4o-mini"
    settings.MODEL_CLOSER_ADVANCED = "gpt-4o"
    settings.JANELA_HISTORICO_RECENTE = 6

    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_PHONE)

        # 1. Criação do Lead
        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_PHONE,
            nome="Dr. Eduardo",
            tipo_entrada=models.TipoEntradaLead.INBOUND,
            origem_canal="WHATSAPP_DIRETO"
        )
        print(f"👤 Lead Criado: ID {lead.id} | Telefone: {lead.telefone} | Nome: {lead.nome}")

        historico_completo = []

        for etapa in ROTEIRO_PERDA:
            turno_num = etapa["turno"]
            msg_cli = etapa["msg_cliente"]

            print("\n" + "-" * 80)
            print(f"📍 TURNO {turno_num}/7 | Cliente ➔ IA")
            print(f"💬 Dr. Eduardo: \"{msg_cli}\"")

            interacao_cli = await LeadRepository.add_interaction(
                db=db,
                lead_id=lead.id,
                origem=models.InteracaoOrigem.CLIENTE,
                texto=msg_cli
            )
            historico_completo.append(interacao_cli)

            historico_janela = await LeadRepository.get_recent_interactions(
                db=db,
                lead_id=lead.id,
                limit=settings.JANELA_HISTORICO_RECENTE
            )

            # 🧠 Analista de Inteligência Comercial (FSM 4D)
            inicio_analista = time.time()
            analise = await analisar_lead_e_fsm(
                lead=lead,
                historico_recente=historico_janela,
                nova_mensagem=msg_cli
            )
            tempo_analista = time.time() - inicio_analista

            if analise.origem_canal_detectada:
                if not lead.origem_canal or lead.origem_canal == "WHATSAPP_DIRETO":
                    lead.origem_canal = analise.origem_canal_detectada

            lead.etapa_funil = analise.etapa_sugerida
            lead.desfecho = analise.desfecho_sugerido
            lead.temperatura = analise.temperatura_sugerida
            lead.resumo_perfil = analise.resumo_perfil
            lead.dados_qualificacao = (
                analise.dados_qualificacao.model_dump()
                if hasattr(analise.dados_qualificacao, "model_dump")
                else analise.dados_qualificacao
            )
            if analise.motivo_perda:
                lead.motivo_perda = analise.motivo_perda
            if analise.valor_estimado:
                lead.valor_estimado = analise.valor_estimado
            if analise.tags_sugeridas:
                tags_set = set(lead.tags or [])
                tags_set.update(analise.tags_sugeridas)
                lead.tags = list(tags_set)

            await db.commit()
            await db.refresh(lead)

            # Modelo de acordo com FinOps
            if lead.etapa_funil in [models.EtapaFunil.NOVO_CONTATO, models.EtapaFunil.QUALIFICACAO]:
                modelo_usado = settings.MODEL_CLOSER_FAST
            else:
                modelo_usado = settings.MODEL_CLOSER_ADVANCED

            print(f"📊 [FSM 4D] ({tempo_analista:.2f}s) | Etapa: {lead.etapa_funil.value} | Desfecho: {lead.desfecho.value} | Temp: {lead.temperatura.value} | Motivo Perda: {lead.motivo_perda} | Modelo: {modelo_usado}")

            # 🤖 Vendedor Comercial ("Seu Zé")
            inicio_vendedor = time.time()
            resposta_vendedor = await gerar_resposta_vendedor(
                nome_cliente_bruto=lead.nome,
                ficha_resumo=lead.resumo_perfil,
                etapa_funil=lead.etapa_funil,
                historico_recente=historico_janela
            )
            tempo_vendedor = time.time() - inicio_vendedor

            print(f"🤖 Seu Zé ({tempo_vendedor:.2f}s): \"{resposta_vendedor}\"")

            interacao_ia = await LeadRepository.add_interaction(
                db=db,
                lead_id=lead.id,
                origem=models.InteracaoOrigem.IA,
                texto=resposta_vendedor
            )
            historico_completo.append(interacao_ia)

        # 2. Executa a Auditoria Comercial Executiva Final
        print("\n" + "=" * 80)
        print("🕵️ EXECUTANDO AGENTE AUDITOR DE NEGÓCIOS (DealAuditorAgent)...")
        print("=" * 80)
        dossie = await auditar_jornada_lead(lead, historico_completo)
        dossie_dict = dossie.model_dump()
        await LeadRepository.salvar_dossie(db, lead, dossie_dict)

        # Salva o arquivo JSON para consulta/inspeção direta
        caminho_json = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "output_dossie_lead_perdido.json"))
        with open(caminho_json, "w", encoding="utf-8") as f:
            json.dump(dossie_dict, f, ensure_ascii=False, indent=2)
        print(f"💾 Snapshot do Dossiê salvo com sucesso em: {caminho_json}")

        # Asserções de Qualidade
        assert lead.desfecho == models.DesfechoLead.PERDIDO, f"Desfecho deveria ser PERDIDO, foi {lead.desfecho}"
        assert lead.etapa_funil in (models.EtapaFunil.NEGOCIACAO, models.EtapaFunil.FECHAMENTO), f"A etapa_funil deve refletir o estágio avançado, foi {lead.etapa_funil}"
        assert dossie.resultado_final.desfecho == schemas.DesfechoLead.PERDIDO
        assert dossie.resultado_final.concorrente_citado is not None
        assert "sol forte" in dossie.resultado_final.concorrente_citado.lower()
        assert dossie.origem_canal == "GOOGLE_SEARCH"
        print("✅ [ORTOGONALIDADE & FSM]: Lead marcado como PERDIDO na etapa de NEGOCIACAO sem apagar histórico!")
        print("✅ [CONCORRÊNCIA IDENTIFICADA]: Concorrente 'Sol Forte Engenharia' rastreado pelo Auditor!")
        print("✅ [CANAL DE ORIGEM]: Canal 'GOOGLE_SEARCH' preservado com sucesso!")

        # Cleanup final
        await cleanup(db, TEST_PHONE)
        print("🧹 Cleanup concluído.")

        return dossie_dict

if __name__ == "__main__":
    asyncio.run(executar_simulacao_perda())
