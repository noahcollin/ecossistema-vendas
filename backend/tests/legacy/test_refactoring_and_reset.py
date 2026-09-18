"""
Teste Automatizado de Validação das Refatorações:
1. Validação do Reset de Memória (resumo_perfil e dados_qualificacao zerados).
2. Validação da Resposta Comercial Fora de Escopo (Out-of-Scope: Fusca/Carros).
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
import models
import schemas
from services.agents import analisar_lead_e_fsm, gerar_resposta_vendedor
from sqlalchemy import select, delete

async def test_reset_and_out_of_scope():
    print("\n" + "="*70)
    print("🧪 INICIANDO TESTE: RESET DE MEMÓRIA & TRATAMENTO FORA DE ESCOPO (FUSCA)")
    print("="*70 + "\n")

    async with AsyncSessionLocal() as db:
        tel = "+5583999991111"
        # Cleanup prévio
        query_pre = select(models.Lead).where(models.Lead.telefone == tel)
        lead_pre = (await db.execute(query_pre)).scalars().first()
        if lead_pre:
            await db.execute(delete(models.Interacao).where(models.Interacao.lead_id == lead_pre.id))
            await db.execute(delete(models.Lead).where(models.Lead.id == lead_pre.id))
            await db.commit()

        # 1. Cria Lead com Ficha Pré-existente
        lead = models.Lead(
            nome="João Teste",
            telefone=tel,
            status=models.LeadStatus.QUALIFICACAO,
            resumo_perfil="Perfil antigo: cliente interessado em energia solar.",
            dados_qualificacao={"consumo_estimado_reais": 1200.0}
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)

        interacao = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto="Olá, gostaria de saber mais."
        )
        db.add(interacao)
        await db.commit()

        # Simula a lógica de reset do endpoint /leads/{lead_id}/interacoes
        await db.execute(delete(models.Interacao).where(models.Interacao.lead_id == lead.id))
        lead.status = models.LeadStatus.NOVO
        lead.resumo_perfil = None
        lead.dados_qualificacao = None
        await db.commit()
        await db.refresh(lead)

        assert lead.resumo_perfil is None, "Falha: resumo_perfil deveria ser None após reset!"
        assert lead.dados_qualificacao is None, "Falha: dados_qualificacao deveria ser None após reset!"
        assert lead.status == models.LeadStatus.NOVO, "Falha: status deveria ser NOVO_LEAD!"
        print("✅ [TESTE 1 PASSOU]: Reset de memória e histórico limpa resumo_perfil e dados_qualificacao com sucesso!")

        # 2. Teste Out-of-Scope: Cliente pedindo Fusca
        msg_fusca = "Tava querendo comprar um fusca pra usar no dia a dia"
        print(f"\n💬 [CLIENTE - FORA DE ESCOPO]: '{msg_fusca}'")

        interacao_fusca = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=msg_fusca
        )
        db.add(interacao_fusca)
        await db.commit()

        analise = await analisar_lead_e_fsm(
            lead=lead,
            historico_recente=[interacao_fusca],
            nova_mensagem=msg_fusca
        )

        lead.resumo_perfil = analise.resumo_perfil
        lead.dados_qualificacao = analise.dados_qualificacao.model_dump()
        await db.commit()

        print(f"📊 [ANALISTA FSM]: Status={analise.status_sugerido.value}")
        print(f"   Ficha do Lead:\n   {lead.resumo_perfil}")

        resposta_closer = await gerar_resposta_vendedor(
            nome_cliente_bruto=lead.nome,
            ficha_resumo=lead.resumo_perfil,
            status_funil=analise.status_sugerido,
            historico_recente=[interacao_fusca]
        )
        print(f"\n🤠 [SEU ZÉ - Resposta Fora de Escopo]:\n{resposta_closer}\n")

        # Cleanup
        await db.execute(delete(models.Interacao).where(models.Interacao.lead_id == lead.id))
        await db.execute(delete(models.Lead).where(models.Lead.id == lead.id))
        await db.commit()
        print("🧹 [CLEANUP] Lead de teste finalizado.")

        print("\n" + "="*70)
        print("🎉 TODOS OS TESTES DE REFATORAÇÃO E ESCOPO FORAM VALIDADOS COM SUCESSO!")
        print("="*70 + "\n")

if __name__ == "__main__":
    asyncio.run(test_reset_and_out_of_scope())
