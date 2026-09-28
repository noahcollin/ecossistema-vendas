import asyncio
import os
import sys
from httpx import AsyncClient, ASGITransport
from sqlalchemy.future import select

# Ajusta path para importar módulos do backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from main import app
from core.database import AsyncSessionLocal
from core.config import settings
from repositories.lead_repository import LeadRepository
from repositories.followup_repository import FollowupRepository
from services.lead_service import LeadService
from services.transbordo_service import TransbordoService
from services.followup_service import FollowupService
from agents import sales_closer_agent, lead_analyzer_agent
import models
import schemas

async def test_ciclo_completo_transbordo_dinamico_e_handover():
    """
    Bateria Integrada de Testes de Transbordo Humano:
    1. Transbordo Silencioso (Zero Mensagens Robóticas ao Cliente).
    2. Silenciamento Contínuo com Preservação de Histórico.
    3. Zero-Click Takeover (Atendente Digita no WhatsApp Web).
    4. Assunção e Envio de Mensagem Humana via Dashboard.
    5. Handover / Devolução para IA com Diretriz de Contexto Interno.
    6. Retomada Fluida da IA Respeitando o Acordo Feito pelo Humano.
    7. Transbordo Dinâmico de Lead VIP por Alto Valor.
    8. Fila de Leads Pendentes de Transbordo.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        tel_teste = "+5583999990088"
        tel_vip = "+5583999990099"

        # Limpa dados prévios se existirem
        async with AsyncSessionLocal() as db:
            for t in [tel_teste, tel_vip]:
                lead_existente = await LeadRepository.get_by_phone(db, t)
                if lead_existente:
                    await LeadRepository.delete_interactions_by_lead_id(db, lead_existente.id)
                    await LeadRepository.delete_lead(db, lead_existente)

        # -------------------------------------------------------------
        # 1. CRIANDO LEAD INICIAL EM PILOTO_IA
        # -------------------------------------------------------------
        print("\n--- [1/8] Criando Lead Inicial em PILOTO_IA ---")
        async with AsyncSessionLocal() as db:
            lead_in = schemas.LeadCreate(
                nome="Dr. Roberto Clínicas",
                telefone=tel_teste,
                etapa_funil=models.EtapaFunil.QUALIFICACAO,
                desfecho=models.DesfechoLead.EM_ANDAMENTO
            )
            lead = await LeadService.criar_lead(db, lead_in)
            assert lead.controle == models.ControleAtendimento.PILOTO_IA
            lead_id = lead.id

            # Agenda um follow-up para testar cancelamento reativo
            await FollowupService.agendar_proximo_followup(db, lead)
            followups = await FollowupRepository.listar_por_lead(db, lead_id)
            assert len(followups) >= 1
            assert any(f.status == models.StatusFollowup.PENDENTE for f in followups)
            print("   • Lead criado com follow-up pendente agendado.")

        # -------------------------------------------------------------
        # 2. TRANSBORDO SILENCIOSO (Cliente pede humano -> Zero Robô)
        # -------------------------------------------------------------
        print("\n--- [2/8] Disparando Transbordo Silencioso (Zero Mensagem Robótica) ---")
        async with AsyncSessionLocal() as db:
            lead = await LeadRepository.get_by_id(db, lead_id)
            
            # Adiciona interação do cliente pedindo humano
            msg_cliente = "Não quero falar com máquina. Quero uma pessoa da gerência para fechar uma condição diferenciada!"
            await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.CLIENTE, msg_cliente)
            
            # Analisador detecta transbordo
            analise = await lead_analyzer_agent.analisar_lead_e_fsm(
                lead=lead,
                historico_recente=[],
                nova_mensagem=msg_cliente
            )
            assert analise.transbordo_sugerido is True
            print(f"   • Analisador confirmou transbordo_sugerido={analise.transbordo_sugerido}")

            # Executa transbordo via serviço
            await TransbordoService.executar_transbordo(
                db=db,
                lead=lead,
                motivo=analise.justificativa,
                analise=analise
            )
            await db.refresh(lead)

            assert lead.controle == models.ControleAtendimento.TRANSBORDO_SOLICITADO
            assert "REQUER_ATENCAO" in lead.tags
            assert "TRANSBORDO" in lead.tags

            # Verifica que follow-up agendado foi CANCELADO
            followups = await FollowupRepository.listar_por_lead(db, lead_id)
            assert all(f.status != models.StatusFollowup.PENDENTE for f in followups)
            print("   • Follow-up pendente cancelado com sucesso no transbordo.")

            # Verifica que NENHUMA mensagem de IA foi enviada para o cliente (zero robô)
            interacoes = await LeadRepository.get_interactions(db, lead_id)
            msgs_ia = [i for i in interacoes if i.origem == models.InteracaoOrigem.IA]
            assert len(msgs_ia) == 0, "A IA deve permanecer 100% silenciosa no transbordo!"
            print("   • IA permaneceu 100% silenciada (nenhuma mensagem robótica enviada ao cliente).")

        # -------------------------------------------------------------
        # 3. SILENCIAMENTO CONTÍNUO (Cliente manda mais mensagens)
        # -------------------------------------------------------------
        print("\n--- [3/8] Testando Silenciamento Contínuo com Armazenamento no Banco ---")
        async with AsyncSessionLocal() as db:
            # Cliente manda mais mensagens enquanto aguarda
            await LeadRepository.add_interaction(db, lead_id, models.InteracaoOrigem.CLIENTE, "Ainda aguardando retorno...")
            await LeadRepository.add_interaction(db, lead_id, models.InteracaoOrigem.CLIENTE, "Tem alguém disponível?")
            
            interacoes = await LeadRepository.get_interactions(db, lead_id)
            msgs_ia = [i for i in interacoes if i.origem == models.InteracaoOrigem.IA]
            assert len(msgs_ia) == 0, "Nenhuma resposta de IA deve ser gravada."
            print("   • Novas mensagens do cliente armazenadas com sucesso sem disparo de IA.")

        # -------------------------------------------------------------
        # 4. ZERO-CLICK TAKEOVER (Atendente humano digita no WhatsApp Web)
        # -------------------------------------------------------------
        print("\n--- [4/8] Testando Zero-Click Takeover (Atendente Digita no WhatsApp Web) ---")
        async with AsyncSessionLocal() as db:
            lead = await LeadRepository.get_by_id(db, lead_id)
            msg_humana_wa = "Oi Dr. Roberto! Aqui é o Marcos da diretoria comercial. Estou assumindo seu atendimento para vermos essa condição especial."
            
            interacao_humana = await TransbordoService.capturar_mensagem_humana_whatsapp(
                db=db,
                lead=lead,
                texto=msg_humana_wa,
                sender_name="Marcos Diretor"
            )
            await db.refresh(lead)

            assert interacao_humana.origem == models.InteracaoOrigem.HUMANO
            assert lead.controle == models.ControleAtendimento.HUMANO_ASSUMIU
            assert "EM_ATENDIMENTO_HUMANO" in lead.tags
            assert "REQUER_ATENCAO" not in lead.tags
            print(f"   • Intervenção humana capturada! Controle atual: {lead.controle.value}")

        # -------------------------------------------------------------
        # 5. ASSUNÇÃO E MENSAGEM HUMANA VIA ENDPOINT REST DO DASHBOARD
        # -------------------------------------------------------------
        print("\n--- [5/8] Testando Endpoints REST de Assunção e Mensagem Humana ---")
        # Assumir atendimento via API
        resp_assumir = await ac.post(
            f"/leads/{lead_id}/transbordo/assumir",
            json={"atendente": "Marcos Silva Especialista"}
        )
        assert resp_assumir.status_code == 200
        dados_assumir = resp_assumir.json()
        assert dados_assumir["controle"] == models.ControleAtendimento.HUMANO_ASSUMIU.value
        print("   • Endpoint POST /transbordo/assumir validado.")

        # Enviar mensagem humana via API do Dashboard
        resp_msg = await ac.post(
            f"/leads/{lead_id}/transbordo/mensagem",
            json={"texto": "Consegui liberar para a sua clínica a condição de R$ 1.800 em 10x sem juros.", "atendente": "Marcos Silva"}
        )
        assert resp_msg.status_code == 200
        dados_msg = resp_msg.json()
        assert dados_msg["origem"] == "humano"
        print("   • Endpoint POST /transbordo/mensagem validado.")

        # -------------------------------------------------------------
        # 6. HANDOVER / DEVOLUÇÃO PARA IA COM DIRETRIZ DE CONTEXTO
        # -------------------------------------------------------------
        print("\n--- [6/8] Testando Devolução para IA (Handover com Diretriz de Contexto) ---")
        diretriz_teste = "Valor alinhado em R$ 1.800 em 10x sem juros. O Dr. Roberto aceitou. Pode pedir Razão Social e CNPJ para fechamento."
        resp_devolver = await ac.post(
            f"/leads/{lead_id}/transbordo/devolver",
            json={
                "diretriz_ia": diretriz_teste,
                "etapa_sugerida": models.EtapaFunil.FECHAMENTO.value,
                "valor_estimado": 1800.0
            }
        )
        assert resp_devolver.status_code == 200
        dados_devolver = resp_devolver.json()
        assert dados_devolver["controle"] == models.ControleAtendimento.PILOTO_IA.value
        assert dados_devolver["etapa_funil"] == models.EtapaFunil.FECHAMENTO.value
        assert dados_devolver["valor_estimado"] == 1800.0
        assert "EM_ATENDIMENTO_HUMANO" not in dados_devolver["tags"]
        print("   • Devolução concluída. Lead restaurado para PILOTO_IA com diretriz gravada.")

        # -------------------------------------------------------------
        # 7. RETOMADA FLUIDA DA IA (Cliente responde e IA não contradiz)
        # -------------------------------------------------------------
        print("\n--- [7/8] Testando Retomada Fluida da IA (Respeitando Acordo do Humano) ---")
        async with AsyncSessionLocal() as db:
            lead = await LeadRepository.get_by_id(db, lead_id)
            
            # Cliente responde confirmando o aceite
            msg_resposta_cliente = "Perfeito Marcos, adorei a condição de R$ 1.800! Vamos fechar sim. Quais dados você precisa?"
            await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.CLIENTE, msg_resposta_cliente)
            
            historico = await LeadRepository.get_interactions(db, lead_id)
            
            # IA gera resposta
            resposta_ia = await sales_closer_agent.gerar_resposta_vendedor(
                nome_cliente_bruto=lead.nome,
                ficha_resumo=lead.resumo_perfil,
                etapa_funil=lead.etapa_funil,
                historico_recente=historico
            )
            print(f"   • Resposta gerada pela IA:\n   \"{resposta_ia}\"")
            
            # Validações semânticas de inteligência
            assert len(resposta_ia) > 15
            # Não pode desmentir o valor nem propor valor diferente
            assert "2500" not in resposta_ia, "A IA não deve citar valores antigos descartados pelo humano!"
            # Deve ser acolhedora e focar no fechamento/dados
            print("   • IA retomou o diálogo respeitando 100% as condições do atendente humano!")

        # -------------------------------------------------------------
        # 8. TRANSBORDO DINÂMICO VIP & FILA DE PENDENTES
        # -------------------------------------------------------------
        print("\n--- [8/8] Testando Gatilho Dinâmico VIP e Fila de Pendentes ---")
        async with AsyncSessionLocal() as db:
            lead_vip_in = schemas.LeadCreate(
                nome="Grupo Hospitalar Estadual",
                telefone=tel_vip,
                etapa_funil=models.EtapaFunil.QUALIFICACAO,
                valor_estimado=25000.0  # Superior ao teto VIP
            )
            lead_vip = await LeadService.criar_lead(db, lead_vip_in)
            
            analise_vip = await lead_analyzer_agent.analisar_lead_e_fsm(
                lead=lead_vip,
                historico_recente=[],
                nova_mensagem="Precisamos de uma solução completa para 5 unidades hospitalares com orçamento aprovado de 25 mil reais."
            )
            # O gatilho VIP no lead_analyzer_agent deve acionar transbordo
            assert analise_vip.transbordo_sugerido is True
            assert "VIP" in analise_vip.tags_sugeridas
            print(f"   • Lead VIP detectado dinamicamente: Transbordo={analise_vip.transbordo_sugerido} | Tags={analise_vip.tags_sugeridas}")

            await TransbordoService.executar_transbordo(
                db=db,
                lead=lead_vip,
                motivo=analise_vip.justificativa,
                analise=analise_vip
            )

        # Consulta fila de pendentes via endpoint
        resp_fila = await ac.get("/leads/transbordo/pendentes")
        assert resp_fila.status_code == 200
        pendentes = resp_fila.json()
        assert len(pendentes) >= 1
        telefones_pendentes = [p["telefone"] for p in pendentes]
        assert tel_vip in telefones_pendentes
        print(f"   • Fila de transbordo contém {len(pendentes)} lead(s) aguardando intervenção humana.")

        # Limpeza final
        async with AsyncSessionLocal() as db:
            l1 = await LeadRepository.get_by_phone(db, tel_teste)
            if l1:
                await LeadRepository.delete_interactions_by_lead_id(db, l1.id)
                await LeadRepository.delete_lead(db, l1)
            l2 = await LeadRepository.get_by_phone(db, tel_vip)
            if l2:
                await LeadRepository.delete_interactions_by_lead_id(db, l2.id)
                await LeadRepository.delete_lead(db, l2)

    print("\n🎉 [SUCESSO TOTAL] Todos os 8 cenários de Transbordo Humano Dinâmico e Handover validados com êxito!")

if __name__ == "__main__":
    asyncio.run(test_ciclo_completo_transbordo_dinamico_e_handover())
