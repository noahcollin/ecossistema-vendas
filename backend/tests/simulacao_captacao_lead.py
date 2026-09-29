"""
Simulação Completa de Ponta a Ponta: Captação de Lead Outbound até Fechamento e Auditoria.
Cenário:
1. Disparo outbound realizado previamente.
2. Lead responde apenas: "Boa tarde."
3. Ingestão Inbound, FSM 4D, Ficha do Lead, Resposta do Vendedor ('Seu Zé').
4. Lead entra em silêncio -> Follow-up Toque 1/3 é gerado e disparado.
5. Lead continua em silêncio -> Follow-up Toque 2/3 é gerado e disparado.
6. Lead reage e pergunta sobre preço/implantação para sua clínica.
7. Negociação com ancoragem de ROI, atualização de memória/ficha e quebra de objeções.
8. Lead aceita fechar -> Etapa FECHAMENTO / GANHO.
9. Mock de Automação de Contratos e Geração do Dossiê Comercial (Deal Auditor).
"""

import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Any, List

from core.database import AsyncSessionLocal
from core.logger import logger
from core.utils import dividir_mensagens_whatsapp
from repositories.lead_repository import LeadRepository
from repositories.followup_repository import FollowupRepository
from services.inbound_service import InboundService
from services.followup_service import FollowupService
from services.lead_service import LeadService
from integrations.redis.buffer import redis_client
import agents
import models


class SimulatedWhatsAppGateway:
    """Gateway simulado que grava todos os disparos com detalhes de balões e delays."""
    def __init__(self):
        self.historico_disparos: List[dict] = []

    async def enviar_presenca(self, telefone: str, presenca: str = "composing", delay_ms: int = 25000) -> dict:
        self.historico_disparos.append({
            "tipo": "presenca",
            "telefone": telefone,
            "presenca": presenca,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return {"status": "sucesso"}

    async def enviar_mensagem(self, telefone: str, texto: str, delay_ms: int = 2000, max_retries: int = 2) -> dict:
        self.historico_disparos.append({
            "tipo": "mensagem_simples",
            "telefone": telefone,
            "texto": texto,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        return {"status": "sucesso", "dados": {"id": f"sim_{len(self.historico_disparos)}"}}

    async def enviar_mensagem_humanizada(
        self,
        telefone: str,
        texto_bruto: str,
        delay_base_ms: int = 1500,
        simular_digitacao: bool = True,
        intervalo_entre_baloes: float = 1.8
    ) -> tuple[list[str], bool]:
        baloes = dividir_mensagens_whatsapp(texto_bruto)
        if not baloes:
            baloes = [texto_bruto.strip()]

        for i, b in enumerate(baloes, 1):
            self.historico_disparos.append({
                "tipo": "balao_whatsapp",
                "telefone": telefone,
                "indice": i,
                "total": len(baloes),
                "texto": b,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        return baloes, True

    async def baixar_arquivo(self, message_id: str, generate_mp3: bool = False) -> dict[str, Any]:
        return {"status": "sucesso", "caminho": "/tmp/mock.bin"}


async def executar_simulacao():
    telefone = "+5583999998888"
    nome_perfil = "Dr. Eduardo Vasconcelos - Clínica Sorriso"
    
    print("\n" + "="*80)
    print("🚀 INICIANDO SIMULAÇÃO COMPLETA DE CAPTAÇÃO E CICLO DE VIDA DO LEAD")
    print("="*80)
    print(f"📱 Telefone Alvo: {telefone}")
    print(f"👤 Nome do Perfil WhatsApp: '{nome_perfil}'")
    print("="*80 + "\n")

    # Injeta o gateway simulado
    gateway = SimulatedWhatsAppGateway()
    InboundService.whatsapp_gateway = gateway
    FollowupService.whatsapp_gateway = gateway

    # 0. Limpeza prévia para garantir ambiente limpo
    async with AsyncSessionLocal() as db:
        lead_existente = await LeadRepository.get_by_phone(db, telefone)
        if lead_existente:
            await FollowupRepository.cancelar_pendentes_por_lead(db, lead_existente.id)
            await db.delete(lead_existente)
            await db.commit()
            print("🧹 Histórico prévio de teste limpo com sucesso no banco de dados.\n")

    # -------------------------------------------------------------------------
    # ETAPA 1: O LEAD RESPONDE AO DISPARO OUTBOUND COM "Boa tarde."
    # -------------------------------------------------------------------------
    print("╔" + "═"*78 + "╗")
    print("║ ETAPA 1: LEAD RESPONDE AO DISPARO OUTBOUND                                  ║")
    print("╚" + "═"*78 + "╝")
    
    # Simula o disparo outbound que havia sido feito previamente
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.create(
            db=db,
            telefone=telefone,
            nome=nome_perfil,
            tipo_entrada=models.TipoEntradaLead.OUTBOUND,
            origem_canal="OUTBOUND_PROSPECCAO",
            etapa_funil=models.EtapaFunil.NOVO_CONTATO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            controle=models.ControleAtendimento.PILOTO_IA,
            temperatura=models.TemperaturaLead.FRIO
        )
        msg_outbound_inicial = (
            "Olá! Aqui é o Seu Zé da Inteligentte Lab. "
            "Estamos ajudando clínicas e consultórios a recuperarem até 30% dos pacientes que tentam agendar à noite e no fim de semana com nossos Agentes de IA no WhatsApp. "
            "Se fizer sentido para o seu momento, só responder por aqui!"
        )
        await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.IA, msg_outbound_inicial)
        await db.commit()

    print(f"📡 [OUTBOUND ENVIADO PREVIAMENTE]:\n\"{msg_outbound_inicial}\"\n")
    print("📩 [WEBHOOK RECEBIDO]: O lead respondeu exatamente: 'Boa tarde.'")
    
    # Processa pelo pipeline Inbound oficial
    async with AsyncSessionLocal() as db:
        await InboundService._executar_pipeline_atendimento(
            db=db,
            telefone=telefone,
            nome_contato=nome_perfil,
            texto_consolidado="Boa tarde."
        )

    # Inspeciona os dados gerados pela IA
    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, telefone)
        followup_pendente = await FollowupRepository.obter_pendente_por_lead(db, lead.id)

    print("\n🔍 [O QUE O SISTEMA EXTRAIU E PROCESSOU NESTE PRIMEIRO CONTATO]:")
    print(f"  • Nome do Lead Salvo: '{lead.nome}'")
    print(f"  • Etapa do Funil (FSM): {lead.etapa_funil.value}")
    print(f"  • Temperatura Cognitiva: {lead.temperatura.value}")
    print(f"  • Ficha / Memória Inicial: {lead.resumo_perfil}")
    print(f"  • Tags Atribuídas: {lead.tags}")
    print(f"  • Próximo Follow-up Agendado: Toque {followup_pendente.tentativa} em {followup_pendente.agendado_para} UTC")

    # Balões disparados pelo Seu Zé
    baloes_etapa1 = [d for d in gateway.historico_disparos if d.get("tipo") == "balao_whatsapp"]
    print(f"\n💬 [RESPOSTA DO SEU ZÉ NO WHATSAPP ({len(baloes_etapa1)} balão(ões))]:")
    for b in baloes_etapa1:
        print(f"   Balão {b['indice']}/{b['total']}: {b['texto']}")

    # -------------------------------------------------------------------------
    # ETAPA 2: O LEAD SILENCIA -> FOLLOW-UP TOQUE 1/3
    # -------------------------------------------------------------------------
    print("\n" + "╔" + "═"*78 + "╗")
    print("║ ETAPA 2: O LEAD NÃO RESPONDE (SILÊNCIO) -> MOTOR DISPARA TOQUE 1/3         ║")
    print("╚" + "═"*78 + "╝")
    print("⏳ Simulando passagem de 4 horas sem resposta do lead...")

    gateway.historico_disparos.clear()
    async with AsyncSessionLocal() as db:
        f1 = await FollowupRepository.obter_pendente_por_lead(db, lead.id)
        # Força o vencimento temporal do agendamento
        f1.agendado_para = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        await db.commit()

        # Aciona o worker de cadência
        await FollowupService.processar_lote_followups(db)

    async with AsyncSessionLocal() as db:
        db.add(f1)
        await db.refresh(f1)
        f2_agendado = await FollowupRepository.obter_pendente_por_lead(db, lead.id)

    baloes_toque1 = [d for d in gateway.historico_disparos if d.get("tipo") == "balao_whatsapp"]
    print(f"\n📡 [CADÊNCIA DE FOLLOW-UP - TOQUE 1/3 DISPARADO]:")
    print(f"  • Status do Toque 1: {f1.status.value}")
    print(f"  • Próximo Agendamento: Toque {f2_agendado.tentativa if f2_agendado else 'Nenhum'}")
    print(f"\n💬 [MENSAGEM ENVIADA NO TOQUE 1 ({len(baloes_toque1)} balão(ões))]:")
    for b in baloes_toque1:
        print(f"   Balão {b['indice']}/{b['total']}: {b['texto']}")

    # -------------------------------------------------------------------------
    # ETAPA 3: O LEAD CONTINUA EM SILÊNCIO -> FOLLOW-UP TOQUE 2/3
    # -------------------------------------------------------------------------
    print("\n" + "╔" + "═"*78 + "╗")
    print("║ ETAPA 3: LEAD CONTINUA EM SILÊNCIO -> MOTOR DISPARA TOQUE 2/3              ║")
    print("╚" + "═"*78 + "╝")
    print("⏳ Simulando passagem de mais 24 horas sem resposta do lead...")

    gateway.historico_disparos.clear()
    async with AsyncSessionLocal() as db:
        f2 = await FollowupRepository.obter_pendente_por_lead(db, lead.id)
        f2.agendado_para = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=10)
        await db.commit()

        # Aciona o worker de cadência
        await FollowupService.processar_lote_followups(db)

    async with AsyncSessionLocal() as db:
        db.add(f2)
        await db.refresh(f2)
        f3_agendado = await FollowupRepository.obter_pendente_por_lead(db, lead.id)

    baloes_toque2 = [d for d in gateway.historico_disparos if d.get("tipo") == "balao_whatsapp"]
    print(f"\n📡 [CADÊNCIA DE FOLLOW-UP - TOQUE 2/3 DISPARADO]:")
    print(f"  • Status do Toque 2: {f2.status.value}")
    print(f"  • Próximo Agendamento na Fila: Toque {f3_agendado.tentativa if f3_agendado else 'Nenhum'}")
    print(f"\n💬 [MENSAGEM ENVIADA NO TOQUE 2 ({len(baloes_toque2)} balão(ões))]:")
    for b in baloes_toque2:
        print(f"   Balão {b['indice']}/{b['total']}: {b['texto']}")

    # -------------------------------------------------------------------------
    # ETAPA 4: LEAD FINALMENTE RESPONDE COM DORES E INTERESSE REAL
    # -------------------------------------------------------------------------
    print("\n" + "╔" + "═"*78 + "╗")
    print("║ ETAPA 4: LEAD REAGE AO TOQUE 2 E TRAZ CONTEXTO COMERCIAL                    ║")
    print("╚" + "═"*78 + "╝")
    msg_lead_retorno = (
        "Boa tarde Seu Zé! Desculpe o sumiço, semana de cirurgias foi muito corrida. "
        "Na verdade me interessa sim. Minhas recepcionistas não dão conta das mensagens no WhatsApp e perdemos muitas consultas no sábado e domingo. "
        "Como funciona a implantação de um agente desse e qual a faixa de investimento?"
    )
    print(f"📩 [MENSAGEM ENVIADA PELO LEAD]:\n\"{msg_lead_retorno}\"\n")

    gateway.historico_disparos.clear()
    async with AsyncSessionLocal() as db:
        await InboundService._executar_pipeline_atendimento(
            db=db,
            telefone=telefone,
            nome_contato=nome_perfil,
            texto_consolidado=msg_lead_retorno
        )

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, telefone)
        f3_status = await FollowupRepository.listar_por_lead(db, lead.id)

    print("🔍 [EVOLUÇÃO DA INTELIGÊNCIA COMERCIAL APÓS A RESPOSTA]:")
    print(f"  • Etapa do Funil (FSM): {lead.etapa_funil.value}")
    print(f"  • Temperatura Cognitiva: {lead.temperatura.value}")
    print(f"  • Nova Ficha do Lead (Memória de Longo Prazo):\n    \"{lead.resumo_perfil}\"")
    print(f"  • Dados de Qualificação Extraídos: {lead.dados_qualificacao}")
    print(f"  • Tags Atualizadas: {lead.tags}")
    cancelados = [f for f in f3_status if f.status == models.StatusFollowup.CANCELADO_POR_RESPOSTA]
    print(f"  • Reatividade da Cadência: {len(cancelados)} follow-up(s) pendente(s) CANCELADO(S) reativamente (RF12).")

    baloes_etapa4 = [d for d in gateway.historico_disparos if d.get("tipo") == "balao_whatsapp"]
    print(f"\n💬 [RESPOSTA DE NEGOCIAÇÃO DO SEU ZÉ ({len(baloes_etapa4)} balão(ões))]:")
    for b in baloes_etapa4:
        print(f"   Balão {b['indice']}/{b['total']}: {b['texto']}")

    # -------------------------------------------------------------------------
    # ETAPA 5: LEAD ACEITA A PROPOSTA E DECIDE FECHAR O CONTRATO
    # -------------------------------------------------------------------------
    print("\n" + "╔" + "═"*78 + "╗")
    print("║ ETAPA 5: LEAD ACEITA PROPOSTA E SOLICITA CONTRATAÇÃO IMEDIATA               ║")
    print("╚" + "═"*78 + "╝")
    msg_lead_fechamento = (
        "Faz todo sentido Seu Zé! O prejuízo de perder 2 ou 3 tratamentos por semana é muito maior que o investimento no Agente. "
        "Quero fechar sim! Podemos emitir o contrato e começar a implantação essa semana?"
    )
    print(f"📩 [MENSAGEM ENVIADA PELO LEAD]:\n\"{msg_lead_fechamento}\"\n")

    gateway.historico_disparos.clear()
    async with AsyncSessionLocal() as db:
        await InboundService._executar_pipeline_atendimento(
            db=db,
            telefone=telefone,
            nome_contato=nome_perfil,
            texto_consolidado=msg_lead_fechamento
        )

    # -------------------------------------------------------------------------
    # ETAPA 6: MOCK DE CONTRATOS & AUDITORIA COMERCIAL EXECUTIVA (DOSSIÊ)
    # -------------------------------------------------------------------------
    print("\n" + "╔" + "═"*78 + "╗")
    print("║ ETAPA 6: AUTOMAÇÃO DE CONTRATOS (MOCK) & AUDITORIA COMERCIAL DO DEAL        ║")
    print("╚" + "═"*78 + "╝")

    async with AsyncSessionLocal() as db:
        lead = await LeadRepository.get_by_phone(db, telefone)
        # Executa a auditoria executiva completa da jornada
        lead_auditado = await LeadService.gerar_dossie_lead(db, lead.id)

    # Simulação da Automação de Contratos
    print("📝 [AUTOMAÇÃO DE CONTRATOS (MOCK INTEGRATION)]:")
    print("   ✓ Minuta contratual gerada automaticamente: CONTRATO-INTELIGENTTE-2026-0929")
    print(f"   ✓ Contratante: Dr. Eduardo Vasconcelos ({lead.nome})")
    print(f"   ✓ Objeto: Implantação e Licenciamento de Agente Autônomo IA 24/7 WhatsApp")
    print(f"   ✓ Valor Estimado no Pipeline: R$ {lead.valor_estimado or 'A Definir'}")
    print(f"   ✓ Link de Assinatura Digital despachado via WhatsApp e e-mail com sucesso.")

    dossie = lead_auditado.dossie_comercial or {}
    print("\n📊 [DOSSIÊ COMERCIAL GERADO PELO DEAL AUDITOR AGENT]:")
    print(f"  • Desfecho Final: {lead.desfecho.value}")
    print(f"  • Nota da Jornada: {dossie.get('nota_atendimento', 'N/A')}/10")
    print(f"  • Resumo Executivo: {dossie.get('resumo_executivo', 'N/A')}")
    print(f"  • Pontos Fortes da Condução: {dossie.get('pontos_fortes', [])}")
    print(f"  • Perfil Psicológico/Comercial do Lead: {dossie.get('perfil_decisor', 'N/A')}")
    print(f"  • Próximos Passos de Onboarding: {dossie.get('proximos_passos', 'N/A')}")

    print("\n" + "="*80)
    print("🎉 SIMULAÇÃO CONCLUÍDA COM 100% DE SUCESSO!")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(executar_simulacao())
