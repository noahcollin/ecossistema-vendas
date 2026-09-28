import asyncio
import os
import sys

# Ajusta path para importar módulos do backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
from core.config import settings
from repositories.lead_repository import LeadRepository
from repositories.followup_repository import FollowupRepository
from services.transbordo_service import TransbordoService
from api.routers.webhook import webhook_uazapi
import models
import schemas


async def testar_humano_inicia_atendimento():
    print("=" * 80)
    print("🧪 TESTE: ATENDIMENTO INICIADO POR HUMANO VIA WHATSAPP (OUTBOUND HUMANO)")
    print("=" * 80)

    telefone_novo = "+5583991112233"
    settings.SANDBOX_MODE = False

    async with AsyncSessionLocal() as db:
        # Limpeza prévia
        lead_existente = await LeadRepository.get_by_phone(db, telefone_novo)
        if lead_existente:
            await FollowupRepository.cancelar_pendentes_por_lead(db, lead_existente.id, models.StatusFollowup.ABORTADO)
            await LeadRepository.delete_interactions_by_lead_id(db, lead_existente.id)
            await LeadRepository.delete_lead(db, lead_existente)

        # ----------------------------------------------------------------------
        # PASSO 1: Atendente humano envia a 1ª mensagem para um número virgem
        # ----------------------------------------------------------------------
        print("\n--- [PASSO 1] Atendente humano envia primeira mensagem no WhatsApp Web ---")
        payload_humano = schemas.UazapiPayload(
            event="messages.upsert",
            chat=schemas.UazapiChat(phone=telefone_novo, name="Dr Felipe"),
            message=schemas.UazapiMessage(
                id="human_msg_outbound_001",
                text="Olá Dr Felipe! Sou o Marcos da Inteligentte. Vi seu interesse no nosso sistema e gostaria de te apresentar uma condição especial.",
                fromMe=True,
                wasSentByApi=False,
                senderName="Marcos Consultor"
            )
        )

        res_humano = await webhook_uazapi(payload_humano)
        print(f"   • Resposta do Webhook: {res_humano}")
        assert res_humano.get("status") == "iniciado_outbound_humano"
        print("   ✅ Webhook reconheceu início de atendimento humano outbound!")

        # Valida que o lead foi criado corretamente no banco
        lead = await LeadRepository.get_by_phone(db, telefone_novo)
        assert lead is not None, "Lead deveria ter sido criado automaticamente!"
        assert lead.tipo_entrada == models.TipoEntradaLead.OUTBOUND, "Tipo deve ser OUTBOUND!"
        assert lead.controle == models.ControleAtendimento.HUMANO_ASSUMIU, "Controle deve ser HUMANO_ASSUMIU!"
        assert "EM_ATENDIMENTO_HUMANO" in lead.tags, "Tag EM_ATENDIMENTO_HUMANO deve estar presente!"
        print(f"   • Lead criado com sucesso no banco: ID {lead.id}")
        print(f"     - Tipo de Entrada: {lead.tipo_entrada.value}")
        print(f"     - Controle: {lead.controle.value}")
        print(f"     - Tags: {lead.tags}")

        # Valida que a mensagem inicial do humano foi persistida
        interacoes = await LeadRepository.get_interactions(db, lead.id)
        assert len(interacoes) >= 1
        msg_humana = [i for i in interacoes if i.origem == models.InteracaoOrigem.HUMANO]
        assert len(msg_humana) == 1
        print(f"   • Mensagem humana gravada no histórico: \"{msg_humana[0].texto[:60]}...\"")
        print("   ✅ [PASSO 1 APROVADO]: Lead criado como OUTBOUND e sob controle HUMANO_ASSUMIU!")

        # ----------------------------------------------------------------------
        # PASSO 2: O cliente responde à mensagem do humano
        # ----------------------------------------------------------------------
        print("\n--- [PASSO 2] Cliente responde ao atendente humano ---")
        payload_cliente = schemas.UazapiPayload(
            event="messages.upsert",
            chat=schemas.UazapiChat(phone=telefone_novo, name="Dr Felipe"),
            message=schemas.UazapiMessage(
                id="client_msg_001",
                text="Olá Marcos! Vi sua mensagem sim, qual é essa condição especial?",
                fromMe=False
            )
        )
        res_cliente = await webhook_uazapi(payload_cliente)
        print(f"   • Resposta do Webhook: {res_cliente}")

        # Aguarda debounce
        print("   ⏳ Aguardando janela de debounce (5s)...")
        await asyncio.sleep(5.5)

        # ----------------------------------------------------------------------
        # PASSO 3: Validação da Blindagem da IA (A IA NÃO DEVE RESPONDER)
        # ----------------------------------------------------------------------
        print("\n--- [PASSO 3] Verificando se a IA permaneceu silenciada ---")
        interacoes_apos_cliente = await LeadRepository.get_interactions(db, lead.id)
        origens = [i.origem for i in interacoes_apos_cliente]
        print(f"   • Total de interações no histórico: {len(interacoes_apos_cliente)}")
        for idx, i in enumerate(interacoes_apos_cliente, 1):
            print(f"     [{idx}] [{i.origem.value.upper()}]: {i.texto[:80]}...")

        # Garante que NENHUMA mensagem de IA foi enviada
        assert models.InteracaoOrigem.IA not in origens, "A IA NÃO deveria ter respondido ao cliente!"
        print("   ✅ A IA permaneceu 100% SILENCIADA! O controle continua com o atendente humano.")

        # Garante que nenhum follow-up foi agendado
        fu_pendente = await FollowupRepository.obter_pendente_por_lead(db, lead.id)
        assert fu_pendente is None, "Nenhum follow-up automático deve existir para lead em atendimento humano!"
        print("   ✅ Nenhum follow-up agendado (controle estritamente humano).")

        # ----------------------------------------------------------------------
        # PASSO 4: O atendente devolve o atendimento para a IA mais tarde
        # ----------------------------------------------------------------------
        print("\n--- [PASSO 4] Atendente conclui sua parte e passa a bola para a IA (Handover) ---")
        lead_devolvido = await TransbordoService.devolver_para_ia(
            db=db,
            lead_id=lead.id,
            diretriz_ia="Apresentei o plano Pro com 10% de desconto. Continuar a negociação.",
            etapa_sugerida=models.EtapaFunil.NEGOCIACAO
        )
        assert lead_devolvido.controle == models.ControleAtendimento.PILOTO_IA
        print(f"   • Lead devolvido para: {lead_devolvido.controle.value}")

        # Valida que agora o follow-up foi ativado para vigiar a ausência
        fu_apos_devolver = await FollowupRepository.obter_pendente_por_lead(db, lead.id)
        assert fu_apos_devolver is not None, "Follow-up deve ser reativado após devolução para a IA!"
        print(f"   • Follow-up rearmado automaticamente pós-handover: ID {fu_apos_devolver.id}")
        print("   ✅ [HANDOVER COM SUCESSO]: A IA assume perfeitamente após a liberação do humano!")

        # Cleanup
        await FollowupRepository.cancelar_pendentes_por_lead(db, lead.id, models.StatusFollowup.ABORTADO)
        await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
        await LeadRepository.delete_lead(db, lead)
        print("\n🧹 Cleanup finalizado com sucesso!")
        print("=" * 80)
        print("🎉 TESTE DE ATENDIMENTO INICIADO POR HUMANO: 100% APROVADO!")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(testar_humano_inicia_atendimento())
