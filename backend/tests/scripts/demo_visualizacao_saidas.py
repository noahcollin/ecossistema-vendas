"""
Demonstração de Saídas Visuais do Ecossistema Comercial
=======================================================
Gera saídas reais completas para visualização:
1. Cenário GANHO: Jornada completa, Ficha do Lead, 4 Dimensões e Dossiê Comercial Executivo.
2. Cenário PERDIDO: Identificação de concorrência, feedback construtivo para a empresa.
3. Cenário TRANSBORDO: Silenciamento da IA e Dica de Ouro estratégica para o atendente humano.
"""

import asyncio
import os
import sys
import json

# Ajusta path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
import models
import schemas
from repositories.lead_repository import LeadRepository
from services.lead_service import LeadService
from services.agents import (
    analisar_lead_e_fsm,
    gerar_resposta_vendedor,
    auditar_jornada_lead,
)

DEMO_PHONE_1 = "+5583991110001"
DEMO_PHONE_2 = "+5583991110002"
DEMO_PHONE_3 = "+5583991110003"

async def cleanup(db, phone: str):
    lead = await LeadRepository.get_by_phone(db, phone)
    if lead:
        await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
        await LeadRepository.delete_lead(db, lead)

async def executar_demo():
    async with AsyncSessionLocal() as db:
        await cleanup(db, DEMO_PHONE_1)
        await cleanup(db, DEMO_PHONE_2)
        await cleanup(db, DEMO_PHONE_3)

        # =====================================================================
        # CENÁRIO 1: NEGÓCIO GANHO (Fechamento Comercial)
        # =====================================================================
        lead_1 = models.Lead(
            nome="Marcos Silveira",
            telefone=DEMO_PHONE_1,
            etapa_funil=models.EtapaFunil.NOVO_CONTATO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.PILOTO_IA,
            temperatura=models.TemperaturaLead.MORNO
        )
        db.add(lead_1)
        await db.commit()
        await db.refresh(lead_1)

        # Diálogo Turno 1
        msg1_cli = "Boa tarde! Sou o Marcos, proprietário de uma churrascaria em João Pessoa. Minha conta de luz veio R$ 4.200 esse mês. Quero ver se energia solar realmente compensa."
        int1_cli = await LeadRepository.add_interaction(db, lead_1.id, models.InteracaoOrigem.CLIENTE, msg1_cli)
        
        analise_1 = await analisar_lead_e_fsm(lead=lead_1, historico_recente=[int1_cli], nova_mensagem=msg1_cli)
        lead_1.resumo_perfil = analise_1.resumo_perfil
        lead_1.dados_qualificacao = analise_1.dados_qualificacao.model_dump()
        lead_1.etapa_funil = analise_1.etapa_sugerida
        lead_1.desfecho = analise_1.desfecho_sugerido
        lead_1.temperatura = analise_1.temperatura_sugerida
        lead_1.valor_estimado = analise_1.valor_estimado
        lead_1.tags = analise_1.tags_sugeridas
        await db.commit()

        resp1_ia = await gerar_resposta_vendedor(
            nome_cliente_bruto=lead_1.nome,
            ficha_resumo=lead_1.resumo_perfil,
            etapa_funil=lead_1.etapa_funil,
            historico_recente=[int1_cli]
        )
        int1_ia = await LeadRepository.add_interaction(db, lead_1.id, models.InteracaoOrigem.IA, resp1_ia)

        # Diálogo Turno 2 (Fechamento)
        msg2_cli = "Excelente explicação, Seu Zé! Tirou minhas dúvidas e a economia é gigante. Quero fechar sim, pode preparar o contrato!"
        int2_cli = await LeadRepository.add_interaction(db, lead_1.id, models.InteracaoOrigem.CLIENTE, msg2_cli)

        analise_2 = await analisar_lead_e_fsm(lead=lead_1, historico_recente=[int1_cli, int1_ia, int2_cli], nova_mensagem=msg2_cli)
        lead_1.resumo_perfil = analise_2.resumo_perfil
        lead_1.etapa_funil = analise_2.etapa_sugerida
        lead_1.desfecho = analise_2.desfecho_sugerido
        lead_1.temperatura = analise_2.temperatura_sugerida
        await db.commit()

        resp2_ia = await gerar_resposta_vendedor(
            nome_cliente_bruto=lead_1.nome,
            ficha_resumo=lead_1.resumo_perfil,
            etapa_funil=lead_1.etapa_funil,
            historico_recente=[int1_cli, int1_ia, int2_cli]
        )
        int2_ia = await LeadRepository.add_interaction(db, lead_1.id, models.InteracaoOrigem.IA, resp2_ia)

        # Auditoria Executiva do Caso Ganho
        historico_1 = [int1_cli, int1_ia, int2_cli, int2_ia]
        dossie_1 = await auditar_jornada_lead(lead_1, historico_1)
        await LeadRepository.salvar_dossie(db, lead_1, dossie_1.model_dump())
        await db.refresh(lead_1)

        # =====================================================================
        # CENÁRIO 2: NEGÓCIO PERDIDO (Causa Raiz & Concorrência)
        # =====================================================================
        lead_2 = models.Lead(
            nome="Carla Fernandes",
            telefone=DEMO_PHONE_2,
            etapa_funil=models.EtapaFunil.NEGOCIACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.PILOTO_IA,
            temperatura=models.TemperaturaLead.MORNO,
            valor_estimado=28000.0,
            tags=["academia", "sensivel_preco"]
        )
        db.add(lead_2)
        await db.commit()
        await db.refresh(lead_2)

        msg_perda = "Seu Zé, obrigado pelo atendimento. Mas fechei com a SolarMais porque eles me deram 20% de desconto e parcelaram em 36x sem juros. Podem cancelar por aí."
        int_perda = await LeadRepository.add_interaction(db, lead_2.id, models.InteracaoOrigem.CLIENTE, msg_perda)

        analise_perda = await analisar_lead_e_fsm(lead=lead_2, historico_recente=[int_perda], nova_mensagem=msg_perda)
        lead_2.etapa_funil = analise_perda.etapa_sugerida
        lead_2.desfecho = analise_perda.desfecho_sugerido
        lead_2.temperatura = analise_perda.temperatura_sugerida
        lead_2.motivo_perda = analise_perda.motivo_perda
        await db.commit()

        dossie_2 = await auditar_jornada_lead(lead_2, [int_perda])
        await LeadRepository.salvar_dossie(db, lead_2, dossie_2.model_dump())
        await db.refresh(lead_2)

        # =====================================================================
        # CENÁRIO 3: TRANSBORDO HUMANO COM DICA DE OURO
        # =====================================================================
        lead_3 = models.Lead(
            nome="Dr. Arnaldo Castro",
            telefone=DEMO_PHONE_3,
            etapa_funil=models.EtapaFunil.NEGOCIACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.PILOTO_IA,
            temperatura=models.TemperaturaLead.QUENTE,
            valor_estimado=45000.0,
            tags=["clinica_medica", "financiamento_bndes"]
        )
        db.add(lead_3)
        await db.commit()
        await db.refresh(lead_3)

        msg_transbordo = "Não adianta IA responder isso, preciso falar com um consultor humano imediatamente para ver enquadramento de linha de crédito do BNDES no CNPJ da minha clínica!"
        int_transbordo = await LeadRepository.add_interaction(db, lead_3.id, models.InteracaoOrigem.CLIENTE, msg_transbordo)

        analise_transbordo = await analisar_lead_e_fsm(lead=lead_3, historico_recente=[int_transbordo], nova_mensagem=msg_transbordo)
        lead_3.controle = models.ControleAtendimento.TRANSBORDO_SOLICITADO
        lead_3.temperatura = analise_transbordo.temperatura_sugerida
        await db.commit()

        dossie_3 = await auditar_jornada_lead(lead_3, [int_transbordo])
        await LeadRepository.salvar_dossie(db, lead_3, dossie_3.model_dump())
        await db.refresh(lead_3)

        # =====================================================================
        # EXIBIÇÃO ESTRUTURADA DE RESULTADOS REAIS
        # =====================================================================
        saidas = {
            "cenario_1_ganho": {
                "cliente": lead_1.nome,
                "telefone": lead_1.telefone,
                "dialogo_whatsapp": [
                    {"de": "Cliente", "texto": msg1_cli},
                    {"de": "Seu Zé (IA)", "texto": resp1_ia},
                    {"de": "Cliente", "texto": msg2_cli},
                    {"de": "Seu Zé (IA)", "texto": resp2_ia},
                ],
                "quatro_dimensoes_lead": {
                    "etapa_funil": lead_1.etapa_funil.value,
                    "desfecho": lead_1.desfecho.value,
                    "controle": lead_1.controle.value,
                    "temperatura": lead_1.temperatura.value,
                    "valor_estimado": lead_1.valor_estimado,
                    "tags": lead_1.tags
                },
                "ficha_do_lead": {
                    "resumo_perfil": lead_1.resumo_perfil,
                    "dados_qualificacao": lead_1.dados_qualificacao
                },
                "dossie_comercial_executivo": lead_1.dossie_comercial
            },
            "cenario_2_perdido": {
                "cliente": lead_2.nome,
                "telefone": lead_2.telefone,
                "motivo_perda": lead_2.motivo_perda,
                "quatro_dimensoes_lead": {
                    "etapa_funil": lead_2.etapa_funil.value,
                    "desfecho": lead_2.desfecho.value,
                    "controle": lead_2.controle.value,
                    "temperatura": lead_2.temperatura.value
                },
                "dossie_comercial_executivo": lead_2.dossie_comercial
            },
            "cenario_3_transbordo": {
                "cliente": lead_3.nome,
                "telefone": lead_3.telefone,
                "quatro_dimensoes_lead": {
                    "etapa_funil": lead_3.etapa_funil.value,
                    "desfecho": lead_3.desfecho.value,
                    "controle": lead_3.controle.value,
                    "temperatura": lead_3.temperatura.value
                },
                "dossie_comercial_executivo": lead_3.dossie_comercial
            }
        }

        # Salva saída em JSON no disco para inspeção
        caminho_saida = os.path.join(os.path.dirname(__file__), "output_visualizacao.json")
        with open(caminho_saida, "w", encoding="utf-8") as f:
            json.dump(saidas, f, ensure_ascii=False, indent=2)

        print("\n" + "="*70)
        print("🎯 DEMONSTRAÇÃO EXECUTADA COM SUCESSO! ARQUIVO GERADO:")
        print(f"   {caminho_saida}")
        print("="*70)

        # Cleanup do banco
        await cleanup(db, DEMO_PHONE_1)
        await cleanup(db, DEMO_PHONE_2)
        await cleanup(db, DEMO_PHONE_3)

if __name__ == "__main__":
    asyncio.run(executar_demo())
