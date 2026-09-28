import asyncio
import os
import sys

# Ajusta sys.path para o root do backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import select, delete
from core.database import AsyncSessionLocal
import models
import schemas
from agents import analisar_lead_e_fsm, gerar_resposta_vendedor, auditar_jornada_lead

async def run_fsm_integration_test():
    print("\n" + "="*70)
    print("🚀 INICIANDO TESTE DE INTEGRAÇÃO: MULTI-AGENTE & FSM MULTIDIMENSIONAL")
    print("="*70 + "\n")

    async with AsyncSessionLocal() as db:
        # 0. Setup: Cria Lead de Teste
        telefone_teste = "+5583988887777"
        
        # Remove lead anterior e interações se existirem
        query_antigo = select(models.Lead).where(models.Lead.telefone == telefone_teste)
        lead_antigo = (await db.execute(query_antigo)).scalars().first()
        if lead_antigo:
            await db.execute(delete(models.Interacao).where(models.Interacao.lead_id == lead_antigo.id))
            await db.execute(delete(models.Lead).where(models.Lead.id == lead_antigo.id))
            await db.commit()

        lead = models.Lead(
            nome="Roberto Padaria",
            telefone=telefone_teste,
            etapa_funil=models.EtapaFunil.NOVO_CONTATO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            temperatura=models.TemperaturaLead.MORNO,
            status=models.LeadStatus.NOVO
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)

        print(f"✅ [SETUP] Lead criado: ID={lead.id} | Etapa={lead.etapa_funil.value} | Desfecho={lead.desfecho.value}\n")

        # -------------------------------------------------------------
        # TURNO 1: Qualificação / Apresentação de Necessidade
        # -------------------------------------------------------------
        msg_1 = (
            "Boa tarde! Sou o Roberto, dono de uma padaria aqui em Campina Grande. "
            "Estou pagando quase R$ 2.500 de luz todo mês e quero reduzir esse custo com energia solar."
        )
        print(f"💬 [CLIENTE - Turno 1]: {msg_1}")

        # Salva interação 1
        interacao_1 = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=msg_1
        )
        db.add(interacao_1)
        await db.commit()

        # Executa Agente 1: Analista
        analise_1 = await analisar_lead_e_fsm(
            lead=lead,
            historico_recente=[interacao_1],
            nova_mensagem=msg_1
        )

        # Atualiza o lead
        lead.resumo_perfil = analise_1.resumo_perfil
        lead.dados_qualificacao = analise_1.dados_qualificacao.model_dump()
        etapa_anterior = lead.etapa_funil
        lead.etapa_funil = analise_1.etapa_sugerida
        lead.desfecho = analise_1.desfecho_sugerido
        lead.temperatura = analise_1.temperatura_sugerida
        await db.commit()

        print(f"📊 [ANALISTA FSM - Turno 1]: {etapa_anterior.value} -> {lead.etapa_funil.value} ({lead.desfecho.value})")
        print(f"   Motivo: {analise_1.justificativa}")
        print(f"   Ficha do Lead:\n   {lead.resumo_perfil}")
        print(f"   Dados JSON: {lead.dados_qualificacao}")

        # Executa Agente 2: Vendedor ("Seu Zé")
        resp_vendedor_1 = await gerar_resposta_vendedor(
            nome_cliente_bruto=lead.nome,
            ficha_resumo=lead.resumo_perfil,
            etapa_funil=lead.etapa_funil,
            historico_recente=[interacao_1]
        )
        print(f"\n🤠 [SEU ZÉ - Resposta 1]:\n{resp_vendedor_1}\n")

        interacao_ia_1 = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.IA,
            texto=resp_vendedor_1
        )
        db.add(interacao_ia_1)
        await db.commit()

        # -------------------------------------------------------------
        # TURNO 2: Objeção de Preço e Garantia
        # -------------------------------------------------------------
        msg_2 = "Gostei da estimativa, Seu Zé! Mas achei o investimento alto e fico com muito receio quanto à garantia dessas placas se quebrar."
        print(f"💬 [CLIENTE - Turno 2]: {msg_2}")

        interacao_2 = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=msg_2
        )
        db.add(interacao_2)
        await db.commit()

        historico_atual = [interacao_1, interacao_ia_1, interacao_2]

        analise_2 = await analisar_lead_e_fsm(
            lead=lead,
            historico_recente=historico_atual,
            nova_mensagem=msg_2
        )

        lead.resumo_perfil = analise_2.resumo_perfil
        lead.dados_qualificacao = analise_2.dados_qualificacao.model_dump()
        etapa_anterior = lead.etapa_funil
        lead.etapa_funil = analise_2.etapa_sugerida
        lead.desfecho = analise_2.desfecho_sugerido
        lead.temperatura = analise_2.temperatura_sugerida
        await db.commit()

        print(f"📊 [ANALISTA FSM - Turno 2]: {etapa_anterior.value} -> {lead.etapa_funil.value} ({lead.desfecho.value})")
        print(f"   Motivo: {analise_2.justificativa}")
        print(f"   Ficha do Lead Atualizada:\n   {lead.resumo_perfil}")

        resp_vendedor_2 = await gerar_resposta_vendedor(
            nome_cliente_bruto=lead.nome,
            ficha_resumo=lead.resumo_perfil,
            etapa_funil=lead.etapa_funil,
            historico_recente=historico_atual
        )
        print(f"\n🤠 [SEU ZÉ - Resposta 2]:\n{resp_vendedor_2}\n")

        interacao_ia_2 = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.IA,
            texto=resp_vendedor_2
        )
        db.add(interacao_ia_2)
        await db.commit()

        # -------------------------------------------------------------
        # TURNO 3: Fechamento Comercial
        # -------------------------------------------------------------
        msg_3 = "Perfeito, me passou muita segurança! Quero fechar sim, Seu Zé. Como fazemos com o contrato?"
        print(f"💬 [CLIENTE - Turno 3]: {msg_3}")

        interacao_3 = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=msg_3
        )
        db.add(interacao_3)
        await db.commit()

        historico_atual = [interacao_1, interacao_ia_1, interacao_2, interacao_ia_2, interacao_3]

        analise_3 = await analisar_lead_e_fsm(
            lead=lead,
            historico_recente=historico_atual,
            nova_mensagem=msg_3
        )

        lead.resumo_perfil = analise_3.resumo_perfil
        lead.dados_qualificacao = analise_3.dados_qualificacao.model_dump()
        etapa_anterior = lead.etapa_funil
        lead.etapa_funil = analise_3.etapa_sugerida
        lead.desfecho = analise_3.desfecho_sugerido
        lead.temperatura = analise_3.temperatura_sugerida
        await db.commit()

        print(f"📊 [ANALISTA FSM - Turno 3]: {etapa_anterior.value} -> {lead.etapa_funil.value} ({lead.desfecho.value})")
        print(f"   Motivo: {analise_3.justificativa}")
        print(f"   Ficha do Lead Atualizada:\n   {lead.resumo_perfil}")

        resp_vendedor_3 = await gerar_resposta_vendedor(
            nome_cliente_bruto=lead.nome,
            ficha_resumo=lead.resumo_perfil,
            etapa_funil=lead.etapa_funil,
            historico_recente=historico_atual
        )
        print(f"\n🤠 [SEU ZÉ - Resposta 3]:\n{resp_vendedor_3}\n")

        # -------------------------------------------------------------
        # AUDITORIA COMERCIAL DO NEGÓCIO FECHADO
        # -------------------------------------------------------------
        print("🕵️ Executando Agente Auditor de Negócios no lead fechado...")
        interacao_ia_3 = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.IA,
            texto=resp_vendedor_3
        )
        historico_completo = historico_atual + [interacao_ia_3]
        dossie = await auditar_jornada_lead(lead, historico_completo)
        print(f"📋 [AUDITOR]: Desfecho={dossie.resultado_final.desfecho.value} | Nota IA={dossie.nota_atendimento_ia}/10")
        print(f"   Estratégia: {dossie.estrategia_utilizada}")
        print(f"   Diferencial Decisivo: {dossie.resultado_final.diferencial_decisivo}")
        print(f"   Dica de Ouro: {dossie.proximo_passo.dica_de_ouro}")
        assert dossie.resultado_final.desfecho in [schemas.DesfechoLead.GANHO, schemas.DesfechoLead.EM_ANDAMENTO]

        # Cleanup final
        await db.execute(delete(models.Interacao).where(models.Interacao.lead_id == lead.id))
        await db.execute(delete(models.Lead).where(models.Lead.id == lead.id))
        await db.commit()
        print("🧹 [CLEANUP] Lead de teste e interações removidos com sucesso!")

        print("\n" + "="*70)
        print("🎉 TESTE MULTI-AGENTE & FSM CONCLUÍDO COM 100% DE SUCESSO!")
        print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(run_fsm_integration_test())
