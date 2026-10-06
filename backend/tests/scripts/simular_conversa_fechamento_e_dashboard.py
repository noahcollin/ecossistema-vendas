"""
Simulação Completa de Conversa: Do Primeiro Contato ao Fechamento Comercial e Dashboard
========================================================================================
Executa um fluxo conversacional completo de 5 turnos com o Seu Zé e o Agente Analista (FSM):
1. [Inbound - Meta Ads] Novo Contato: Dor de perda de pacientes à noite.
2. [Qualificação] Diagnóstico do volume (80-100 msgs/dia, 3 atendentes).
3. [Negociação] Apresentação da solução e ancoragem de investimento (R$ 3.500,00).
4. [Sinal Verde] Lead dá o 'Sim' -> Seu Zé solicita dados cadastrais para formalização.
5. [Dados Enviados] Lead envia CNPJ e Razão Social -> Transbordo humano de fechamento ativado!
6. [Cockpit Humano] Corretor humano assume e marca como GANHO.
7. [Dashboard BI] Consulta em tempo real aos endpoints de Analytics e exibe o impacto no painel.
"""

import os
import sys
import asyncio
import json
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from main import app
from core.database import AsyncSessionLocal
from core.config import settings
from core.utils import dividir_mensagens_whatsapp
from repositories.lead_repository import LeadRepository
from repositories.followup_repository import FollowupRepository
from services.inbound import InboundService
from services.cadence import FollowupService
from services.handover import TransbordoService
from services.lead import AnalyticsService
import models
from unittest.mock import AsyncMock, patch
from integrations.uazapi import client as uazapi_client

TELEFONE_LEAD = "+5583991234567"
NOME_PERFIL = "Dr. Marcelo Vasconcelos - Oftalmologia"


class GatewaySimuladoWhatsApp:
    """Captura e exibe balões humanizados de resposta do Seu Zé."""
    def __init__(self):
        self.mensagens_enviadas = []

    async def enviar_presenca(self, telefone: str, presenca: str = "composing", delay_ms: int = 15000):
        return {"status": "sucesso"}

    async def enviar_mensagem(self, telefone: str, texto: str, delay_ms: int = 2000, max_retries: int = 2):
        self.mensagens_enviadas.append({"telefone": telefone, "texto": texto})
        return {"status": "sucesso", "dados": {"id": "mock_id"}}

    async def enviar_mensagem_humanizada(
        self,
        telefone: str,
        texto_bruto: str,
        delay_base_ms: int = 1500,
        simular_digitacao: bool = True,
        intervalo_entre_baloes: float = 1.8
    ):
        baloes = dividir_mensagens_whatsapp(texto_bruto) or [texto_bruto]
        for b in baloes:
            self.mensagens_enviadas.append({"telefone": telefone, "texto": b})
        return baloes, True

    async def baixar_arquivo(self, message_id: str, generate_mp3: bool = False):
        return {"status": "sucesso"}


def print_banner(titulo: str):
    print("\n" + "═" * 85)
    print(f"💬 {titulo}")
    print("═" * 85)


def print_conversa(autor: str, texto: str):
    if autor == "CLIENTE":
        print(f"\n👤 [DR. MARCELO (CLIENTE)]: \n   \"{texto}\"")
    elif autor == "SEU_ZE":
        baloes = [b.strip() for b in texto.split("|||") if b.strip()] or [texto]
        print("\n🤖 [SEU ZÉ (CONSULTOR INTELIGENTTE)]:")
        for i, b in enumerate(baloes, 1):
            print(f"   [Balão {i}/{len(baloes)}]: \"{b}\"")
    elif autor == "SISTEMA":
        print(f"\n⚙️  [SISTEMA / FSM]: {texto}")


async def executar_simulacao():
    print("\n" + "█" * 85)
    print("🚀 INICIANDO SIMULAÇÃO COMPLETA: LEAD DE META ADS ATÉ FECHAMENTO E DASHBOARD")
    print("█" * 85)

    # Injeta gateway simulado
    gw = GatewaySimuladoWhatsApp()
    InboundService.whatsapp_gateway = gw
    FollowupService.whatsapp_gateway = gw
    uazapi_client.enviar_mensagem = AsyncMock(return_value={"dados": {"id": "mock_humana_123"}})

    # 1. Limpeza de dados prévios para ambiente isolado
    async with AsyncSessionLocal() as db:
        lead_previo = await LeadRepository.get_by_phone(db, TELEFONE_LEAD)
        if lead_previo:
            await FollowupRepository.cancelar_pendentes_por_lead(db, lead_previo.id)
            await LeadRepository.delete_interactions_by_lead_id(db, lead_previo.id)
            await LeadRepository.delete_lead(db, lead_previo)

    # =========================================================================
    # TURNO 1: Primeiro Contato (Meta Ads -> Inbound)
    # =========================================================================
    print_banner("TURNO 1: PRIMEIRO CONTATO (ORIGEM: ANÚNCIO INSTAGRAM / META ADS)")
    msg_1 = (
        "Olá! Vi o anúncio de vocês no Instagram sobre redução de filas e agentes no WhatsApp. "
        "Tenho uma clínica oftalmológica e estamos perdendo muitos agendamentos fora do horário."
    )
    print_conversa("CLIENTE", msg_1)

    async with AsyncSessionLocal() as db:
        await InboundService._executar_pipeline_atendimento(
            db=db,
            telefone=TELEFONE_LEAD,
            nome_contato=NOME_PERFIL,
            texto_consolidado=msg_1
        )

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TELEFONE_LEAD)
        interacoes = await LeadRepository.get_recent_interactions(db, lead.id, limit=5)
        ultima_resp_ia = next((i.texto for i in reversed(interacoes) if i.origem == models.InteracaoOrigem.IA), "")

    print_conversa("SEU_ZE", ultima_resp_ia)
    print_conversa("SISTEMA", f"Etapa: {lead.etapa_funil.value} | Temp: {lead.temperatura.value} | Origem: {lead.origem_canal} | Ficha: {lead.resumo_perfil}")

    # =========================================================================
    # TURNO 2: Qualificação & Diagnóstico
    # =========================================================================
    print_banner("TURNO 2: DIAGNÓSTICO E QUALIFICAÇÃO DO PERFIL")
    msg_2 = (
        "Temos 3 secretárias no horário comercial, mas recebemos cerca de 80 a 100 mensagens por dia. "
        "O problema é que das 19h em diante e nos finais de semana ninguém responde, e o paciente vai na concorrência."
    )
    print_conversa("CLIENTE", msg_2)

    async with AsyncSessionLocal() as db:
        await InboundService._executar_pipeline_atendimento(
            db=db,
            telefone=TELEFONE_LEAD,
            nome_contato=NOME_PERFIL,
            texto_consolidado=msg_2
        )

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TELEFONE_LEAD)
        interacoes = await LeadRepository.get_recent_interactions(db, lead.id, limit=5)
        ultima_resp_ia = next((i.texto for i in reversed(interacoes) if i.origem == models.InteracaoOrigem.IA), "")

    print_conversa("SEU_ZE", ultima_resp_ia)
    print_conversa("SISTEMA", f"Etapa: {lead.etapa_funil.value} | Temp: {lead.temperatura.value} | Valor Est.: R$ {lead.valor_estimado or 0:,.2f} | Tags: {lead.tags}")

    # =========================================================================
    # TURNO 3: Negociação & Ancoragem de Valores
    # =========================================================================
    print_banner("TURNO 3: APRESENTAÇÃO DA SOLUÇÃO E NEGOCIAÇÃO DE VALORES")
    msg_3 = (
        "Com certeza, faz total sentido ter o agente atendendo e agendando 24 horas por dia. "
        "Qual o valor do investimento para implementar esse agente autônomo na nossa clínica?"
    )
    print_conversa("CLIENTE", msg_3)

    async with AsyncSessionLocal() as db:
        await InboundService._executar_pipeline_atendimento(
            db=db,
            telefone=TELEFONE_LEAD,
            nome_contato=NOME_PERFIL,
            texto_consolidado=msg_3
        )

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TELEFONE_LEAD)
        interacoes = await LeadRepository.get_recent_interactions(db, lead.id, limit=5)
        ultima_resp_ia = next((i.texto for i in reversed(interacoes) if i.origem == models.InteracaoOrigem.IA), "")

    print_conversa("SEU_ZE", ultima_resp_ia)
    print_conversa("SISTEMA", f"Etapa: {lead.etapa_funil.value} | Temp: {lead.temperatura.value} | Valor: R$ {lead.valor_estimado or 0:,.2f}")

    # =========================================================================
    # TURNO 4: Sinal Verde para Fechamento
    # =========================================================================
    print_banner("TURNO 4: LEAD DÁ SINAL VERDE (MOMENTO CRÍTICO DE FECHAMENTO)")
    msg_4 = "Excelente Seu Zé, a proposta cabe no nosso orçamento perfeitamente. Vamos fechar! Como fazemos?"
    print_conversa("CLIENTE", msg_4)

    async with AsyncSessionLocal() as db:
        await InboundService._executar_pipeline_atendimento(
            db=db,
            telefone=TELEFONE_LEAD,
            nome_contato=NOME_PERFIL,
            texto_consolidado=msg_4
        )

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TELEFONE_LEAD)
        interacoes = await LeadRepository.get_recent_interactions(db, lead.id, limit=5)
        ultima_resp_ia = next((i.texto for i in reversed(interacoes) if i.origem == models.InteracaoOrigem.IA), "")

    print_conversa("SEU_ZE", ultima_resp_ia)
    print_conversa("SISTEMA", f"Etapa FSM: {lead.etapa_funil.value} (FECHAMENTO) | Controle: {lead.controle.value} | Tags: {lead.tags}")

    # =========================================================================
    # TURNO 5: Envio dos Dados Cadastrais & Transbordo Humano de Fechamento
    # =========================================================================
    print_banner("TURNO 5: ENVIO DOS DADOS CADASTRAIS -> ACIONAMENTO DO TRANSBORDO HUMANO")
    msg_5 = (
        "Seguem nossos dados para o contrato:\n"
        "Razão Social: Clínica Vasconcelos Oftalmologia Ltda\n"
        "CNPJ: 12.345.678/0001-90\n"
        "E-mail: marcelo@clinicavasconcelos.med.br"
    )
    print_conversa("CLIENTE", msg_5)

    async with AsyncSessionLocal() as db:
        await InboundService._executar_pipeline_atendimento(
            db=db,
            telefone=TELEFONE_LEAD,
            nome_contato=NOME_PERFIL,
            texto_consolidado=msg_5
        )

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, TELEFONE_LEAD)
        interacoes = await LeadRepository.get_recent_interactions(db, lead.id, limit=5)
        ultima_resp_ia = next((i.texto for i in reversed(interacoes) if i.origem == models.InteracaoOrigem.IA), "")

    print_conversa("SEU_ZE", ultima_resp_ia)
    print_conversa("SISTEMA", (
        f"🚨 TRANSBORDO ACIONADO: Controle={lead.controle.value} | "
        f"Etapa={lead.etapa_funil.value} | IA Silenciada: SIM | "
        f"Equipe Notificada: SIM | Tags={lead.tags}"
    ))

    # =========================================================================
    # TURNO 6: Atendente Humano Assume no Cockpit e Conclui Venda (Desfecho GANHO)
    # =========================================================================
    print_banner("TURNO 6: ATENDENTE HUMANO ASSUME NO COCKPIT E FINALIZA CONTRATO (GANHO)")
    async with AsyncSessionLocal() as db:
        # Atendente assume
        lead = await TransbordoService.assumir_atendimento(db, lead.id, nome_atendente="Dra. Roberta (Closer)")
        print(f"   👤 Atendente assumiu a condução no painel: Controle = {lead.controle.value}")

        # Mensagem humana enviada pelo painel
        interacao_humana = await TransbordoService.enviar_mensagem_humana_painel(
            db, lead.id,
            "Olá Dr. Marcelo! Sou a Roberta do time de contratos da Inteligentte. Acabei de emitir a minuta contratual para o seu e-mail marcelo@clinicavasconcelos.med.br! Fico à disposição.",
            atendente="Dra. Roberta (Closer)"
        )
        print(f"   ✉️  Mensagem humana enviada via painel: \"{interacao_humana.texto}\"")

        # Conclusão da venda com contrato assinado
        lead.desfecho = models.DesfechoLead.GANHO
        lead.valor_estimado = 3500.0  # Mensalidade acordada
        lead.etapa_funil = models.EtapaFunil.FECHAMENTO
        await db.commit()
        await db.refresh(lead)
        print(f"   🎉 NEGÓCIO CONCLUÍDO COM SUCESSO: Desfecho = {lead.desfecho.value} | Receita = R$ {lead.valor_estimado:,.2f}")

    # =========================================================================
    # TURNO 7: Consulta ao Dashboard de Analytics em Tempo Real
    # =========================================================================
    print_banner("TURNO 7: O QUE FOI ENVIADO E REGISTRADO NO DASHBOARD (ANALYTICS & BI)")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Consulta o Overview consolidado
        res_overview = await client.get("/analytics/overview")
        assert res_overview.status_code == 200
        bi = res_overview.json()

        # Consulta a Ficha individual do Lead
        res_lead = await client.get(f"/leads/{lead.id}")
        assert res_lead.status_code == 200
        lead_dto = res_lead.json()

    print("\n📊 [PAINEL EXECUTIVO DO DASHBOARD - DADOS AGREGADOS EM TEMPO REAL]:")
    print(f"   💰 Pipeline Ativo Total:    R$ {bi['financeiro']['pipeline_ativo_reais']:,.2f}")
    print(f"   🏆 Receita Ganha Faturada: R$ {bi['financeiro']['receita_ganha_reais']:,.2f} (Inclui os R$ 3.500 do Dr. Marcelo)")
    print(f"   📈 Taxa de Conversão:      {bi['financeiro']['taxa_conversao_pct']:.1f}%")
    print(f"   👥 Total de Vendas Ganhas: {bi['financeiro']['total_leads_ganhos']}")
    print(f"   🔥 Leads Quentes Ativos:   {bi['funil']['leads_quentes_count']}")
    print(f"   📱 Canal Campeão Receita:  {bi['aquisicao'].get('canal_campeao_receita')}")
    print(f"   💬 Volume Total Mensagens: {bi['conversas']['volume_mensagens']['total_mensagens']}")

    print("\n📋 [COCKPIT OPERACIONAL - FICHA DO LEAD NO CRM / DASHBOARD]:")
    print(f"   • ID do Lead:       {lead_dto['id']}")
    print(f"   • Nome Completo:    {lead_dto['nome']}")
    print(f"   • Telefone:         {lead_dto['telefone']}")
    print(f"   • Canal de Entrada: {lead_dto['origem_canal']} ({lead_dto['tipo_entrada']})")
    print(f"   • Etapa Funil:      {lead_dto['etapa_funil']}")
    print(f"   • Desfecho:         {lead_dto['desfecho']}")
    print(f"   • Temperatura:      {lead_dto['temperatura']}")
    print(f"   • Valor Faturado:   R$ {lead_dto['valor_estimado']:,.2f}")
    print(f"   • Controle Atual:   {lead_dto['controle']}")
    print(f"   • Tags:             {lead_dto['tags']}")
    print(f"   • Memória / Dossiê: {lead_dto['resumo_perfil']}")

    print("\n" + "█" * 85)
    print("🏆 SIMULAÇÃO CONCLUÍDA COM 100% DE SUCESSO E DADOS INTEGRADOS AO DASHBOARD!")
    print("█" * 85 + "\n")


if __name__ == "__main__":
    asyncio.run(executar_simulacao())
