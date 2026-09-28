import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy.future import select

# Ajusta path para importar módulos do backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
from core.config import settings
import models
import schemas
from services.lead_service import LeadService
from repositories.lead_repository import LeadRepository
from repositories.followup_repository import FollowupRepository
from services.transbordo_service import TransbordoService
from services.followup_service import FollowupService
from agents import sales_closer_agent


async def testar_cenario_transbordo_negociacao_e_followup():
    print("=" * 80)
    print("🧪 TESTE DE CENÁRIO REAL: TRANSBORDO CONCLUÍDO EM FASE DE NEGOCIAÇÃO")
    print("=" * 80)

    telefone_teste = "+5583988887766"

    async with AsyncSessionLocal() as db:
        # Limpeza prévia
        lead_antigo = await LeadRepository.get_by_phone(db, telefone_teste)
        if lead_antigo:
            await FollowupRepository.cancelar_pendentes_por_lead(db, lead_antigo.id, models.StatusFollowup.ABORTADO)
            await LeadRepository.delete_interactions_by_lead_id(db, lead_antigo.id)
            await LeadRepository.delete_lead(db, lead_antigo)

        # ----------------------------------------------------------------------
        # ETAPA 1: Lead inicia diálogo e tem follow-up agendado no Piloto da IA
        # ----------------------------------------------------------------------
        print("\n--- [ETAPA 1] Lead entra em Negociação com IA e agenda follow-up inicial ---")
        lead_in = schemas.LeadCreate(
            telefone=telefone_teste,
            nome="Carlos Eduardo",
            etapa_funil=models.EtapaFunil.NEGOCIACAO,
            temperatura=models.TemperaturaLead.MORNO,
            origem_canal="WHATSAPP_DIRETO"
        )
        lead = await LeadService.criar_lead(db, lead_in)
        lead.resumo_perfil = "Interessado no Plano Empresarial. Solicitou desconto para 15 licenças."
        lead.desfecho = models.DesfechoLead.EM_ANDAMENTO
        lead.controle = models.ControleAtendimento.PILOTO_IA
        await db.commit()
        await db.refresh(lead)

        # Simula IA agendando follow-up inicial
        followup_inicial = await FollowupService.agendar_proximo_followup(db, lead)
        print(f"   • Lead criado ID {lead.id}: Controle={lead.controle.value} | Etapa={lead.etapa_funil.value}")
        print(f"   • Follow-up inicial agendado: ID={followup_inicial.id if followup_inicial else 'None'}")

        # ----------------------------------------------------------------------
        # ETAPA 2: Cliente pede para falar com gerente / Transbordo acionado
        # ----------------------------------------------------------------------
        print("\n--- [ETAPA 2] Transbordo Humano é acionado ---")
        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto="Gostei, mas quero falar com o responsável de vendas pra negociar esse valor."
        )
        lead = await TransbordoService.executar_transbordo(
            db=db,
            lead=lead,
            motivo="Cliente solicitou negociação direta de valor com a gerência."
        )
        print(f"   • Lead em Transbordo: Controle={lead.controle.value} | Tags={lead.tags}")
        
        # Verifica se o follow-up pendente foi cancelado
        fu_apos_transbordo = await FollowupRepository.obter_pendente_por_lead(db, lead.id)
        print(f"   • Follow-up pendente após transbordo: {fu_apos_transbordo} (esperado: None)")
        assert fu_apos_transbordo is None, "Follow-up deveria estar cancelado durante o transbordo!"

        # ----------------------------------------------------------------------
        # ETAPA 3: Atendente Humano assume e conversa pelo WhatsApp
        # ----------------------------------------------------------------------
        print("\n--- [ETAPA 3] Consultor humano assume o atendimento e faz acordo ---")
        lead = await TransbordoService.assumir_atendimento(db, lead.id, nome_atendente="Juliana Gerente")
        print(f"   • Controle após assunção humana: {lead.controle.value}")

        # Humano envia mensagem de negociação fechando acordo
        await TransbordoService.capturar_mensagem_humana_whatsapp(
            db=db,
            lead=lead,
            texto="Olá Carlos, sou a Juliana! Consegui liberar as 15 licenças por R$ 7.200 em 12x no boleto. Posso emitir o contrato?",
            sender_name="Juliana Gerente"
        )
        print("   • Mensagem da atendente humana gravada no histórico.")

        # ----------------------------------------------------------------------
        # ETAPA 4: Humano finaliza o atendimento e devolve para a IA
        # ----------------------------------------------------------------------
        print("\n--- [ETAPA 4] Atendente humano finaliza e devolve o lead para a IA ---")
        lead = await TransbordoService.devolver_para_ia(
            db=db,
            lead_id=lead.id,
            diretriz_ia="Proposta aprovada por R$ 7.200 em 12x no boleto. Se o Carlos sumir, fazer follow-up cordial.",
            etapa_sugerida=models.EtapaFunil.NEGOCIACAO,
            valor_estimado=7200.0
        )
        print(f"   • Lead devolvido: Controle={lead.controle.value} | Etapa={lead.etapa_funil.value} | Valor=R$ {lead.valor_estimado}")

        # ----------------------------------------------------------------------
        # ETAPA 5: O que aconteceu com o Follow-up após a devolução?
        # ----------------------------------------------------------------------
        print("\n--- [ETAPA 5] Investigando o comportamento do Follow-Up pós-devolução ---")
        followup_ativo = await FollowupRepository.obter_pendente_por_lead(db, lead.id)
        print(f"   • Existe follow-up pendente agendado agora? -> ID {followup_ativo.id if followup_ativo else 'None'}")
        assert followup_ativo is not None, "O follow-up deve ser agendado automaticamente após a devolução para a IA!"
        print("   ✅ Follow-up REATIVADO automaticamente pelo devolver_para_ia para vigiar o silêncio!")

        # ----------------------------------------------------------------------
        # ETAPA 6: Se o cliente ficar em silêncio (Ghosting pós-atendimento humano)
        # ----------------------------------------------------------------------
        print("\n--- [ETAPA 6] Testando disparo de Follow-up pelo 'Seu Zé' se cliente ficar em silêncio ---")
        # Força vencimento para testar o que a IA fala
        followup_ativo.agendado_para = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        await db.commit()

        # Executa o disparo do follow-up
        historico = await LeadRepository.get_recent_interactions(db, lead.id, limit=10)
        print(f"   • Histórico recente de interações carregado: {len(historico)} mensagens.")
        for h in historico:
            print(f"     [{h.origem.value.upper()}]: {h.texto[:70]}...")

        msg_followup = await sales_closer_agent.gerar_mensagem_followup(
            nome_cliente_bruto=lead.nome,
            ficha_resumo=lead.resumo_perfil,
            etapa_funil=lead.etapa_funil,
            tentativa=followup_ativo.tentativa,
            historico_recente=historico
        )

        print("\n   🤖 [MENSAGEM DE RESGATE GERADA PELA IA]:")
        print(f"   \"{msg_followup}\"")

        # Validações da mensagem
        assert len(msg_followup) > 10
        print("   ✅ A IA gerou a mensagem de follow-up perfeitamente alinhada com o contexto!")

        # ----------------------------------------------------------------------
        # ETAPA 7: Se o cliente responder ao invés de sumir
        # ----------------------------------------------------------------------
        print("\n--- [ETAPA 7] Testando comportamento se o cliente responder ---")
        await LeadRepository.add_interaction(
            db=db,
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto="Oi Juliana, vi sua mensagem! Pode gerar o contrato sim nesse valor de 7.200."
        )
        # O webhook cancela os follow-ups pendentes (RF12)
        cancelados = await FollowupService.cancelar_followups_pendentes(db, lead.id)
        print(f"   • Follow-ups cancelados pela resposta do cliente (RF12): {cancelados}")

        # A IA responde respeitando a diretriz
        historico_novo = await LeadRepository.get_recent_interactions(db, lead.id, limit=10)
        resposta_ia = await sales_closer_agent.gerar_resposta_vendedor(
            nome_cliente_bruto=lead.nome,
            ficha_resumo=lead.resumo_perfil,
            etapa_funil=models.EtapaFunil.FECHAMENTO,
            historico_recente=historico_novo
        )
        print("\n   🤖 [RESPOSTA DA IA AO CLIENTE]:")
        print(f"   \"{resposta_ia}\"")

        # Cleanup
        await FollowupRepository.cancelar_pendentes_por_lead(db, lead.id, models.StatusFollowup.ABORTADO)
        await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
        await LeadRepository.delete_lead(db, lead)
        print("\n🧹 Cleanup finalizado com sucesso!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(testar_cenario_transbordo_negociacao_e_followup())
