"""
CHAOS ENGINEERING & RED TEAMING TEST SUITE
==========================================
Esta suíte valida as correções de fragilidades:
1. Condição de corrida em criação simultânea de Leads (IntegrityError resiliente).
2. Sanitização de bytes nulos (\\x00) e caracteres tóxicos no PostgreSQL.
3. Blindagem de Jitter e Horário Comercial (não vazar mensagens fora de expediente).
4. Deriva de relógio e timestamps futuros.
5. Payloads complexos e serialização no Webhook.
6. Proteção estrita de Opt-out (LGPD).
"""

import asyncio
import os
import sys
import json
from datetime import datetime, timezone, timedelta

# Adiciona o diretório backend ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
from core.config import settings
from core.temporal import BusinessHoursPolicy
import models
import schemas
from repositories.lead_repository import LeadRepository
from services.inbound_service import InboundService
from services.transbordo_service import TransbordoService
from api.routers.webhook import webhook_uazapi

CHAOS_PREFIX = "+558393333"


async def cleanup_chaos_leads():
    async with AsyncSessionLocal() as db:
        leads = await LeadRepository.list_all(db)
        for lead in leads:
            if lead.telefone and CHAOS_PREFIX in lead.telefone:
                await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
                await LeadRepository.delete_lead(db, lead)


async def test_1_race_condition_duplicacao_simultanea():
    print("\n--- [1/6] Testando Condição de Corrida: Criação Concorrente Resiliente ---")
    tel = f"{CHAOS_PREFIX}0001"
    
    # 10 corrotinas simultâneas chamando create diretamente no mesmo milissegundo
    async def tentar_criar_direto(i: int):
        async with AsyncSessionLocal() as db:
            lead = await LeadRepository.create(db, tel, f"Carlos Concorrente {i}")
            return lead.id

    resultados = await asyncio.gather(*(tentar_criar_direto(i) for i in range(10)))
    print(f"   • 10 tentativas simultâneas retornaram IDs: {resultados}")
    
    # Todos devem apontar para o mesmo ID único e sem levantar IntegrityError
    assert len(set(resultados)) == 1, "Todas as 10 chamadas devem convergir para o mesmo Lead ID!"
    assert None not in resultados
    print("✅ [BLINDAGEM 1 APROVADA]: Condição de corrida absorvida graciosamente pelo LeadRepository!")


async def test_2_caracteres_toxicos_e_bytes_nulos():
    print("\n--- [2/6] Testando Sanitização de Bytes Nulos (\\x00) e Unicode Extremo ---")
    tel = f"{CHAOS_PREFIX}0002"
    async with AsyncSessionLocal() as db:
        lead = await InboundService._obter_ou_criar_lead(db, tel, "Testador Tóxico")
        
        # 1. Byte nulo (que antes quebrava o Postgres com CharacterNotInRepertoireError)
        texto_nulo = "Olá\x00mundo\x00com\x00bytes\x00nulos!"
        interacao = await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.CLIENTE, texto_nulo)
        
        print(f"   • Texto salvo no banco: '{interacao.texto}'")
        assert "\x00" not in interacao.texto, "Bytes nulos devem ser purgados antes do insert no Postgres!"
        assert interacao.texto == "Olámundocombytesnulos!"

        # 2. Bidi override e caracteres invisíveis
        texto_bidi = "\u202e\u202d\u200e\u200fTexto Invertido e Caracteres Invisíveis\u200b\u200c"
        interacao_bidi = await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.CLIENTE, texto_bidi)
        assert interacao_bidi.id is not None
        print("✅ [BLINDAGEM 2 APROVADA]: Bytes nulos sanitizados e caracteres extremos persistidos com sucesso!")


async def test_3_jitter_e_horario_comercial():
    print("\n--- [3/6] Testando Blindagem de Jitter e Horário Comercial (Anti-Vazamento) ---")
    # Caso crítico: Sexta-feira às 18:25 (dentro do expediente) com 15 min de jitter
    # Anteriormente vazava para Sexta 18:40 (fora do expediente). Agora deve ir para Sábado de manhã!
    sexta_1825_utc = datetime(2026, 9, 25, 21, 25)  # 18:25 em Brasília
    res_sexta = BusinessHoursPolicy.ajustar_para_horario_comercial(sexta_1825_utc, indice_dispersao=5)
    res_sexta_local = res_sexta + BusinessHoursPolicy.OFFSET_BRASIL
    
    print(f"   • Sexta 18:25 + Jitter 15min -> {res_sexta_local.strftime('%A %d/%m %H:%M:%S')}")
    assert res_sexta_local.weekday() == 5, "Deve ser postergado para Sábado!"
    assert res_sexta_local.time() >= BusinessHoursPolicy._parse_hhmm("09:00"), "Deve ser dentro do horário de Sábado!"
    assert res_sexta_local.time() <= BusinessHoursPolicy._parse_hhmm("12:30"), "Não pode ultrapassar 12:30 de Sábado!"

    # Caso crítico 2: Sábado às 12:25 com 15 min de jitter -> deve ir para Segunda 08:35 + jitter
    sabado_1225_utc = datetime(2026, 9, 26, 15, 25)  # 12:25 em Brasília
    res_sabado = BusinessHoursPolicy.ajustar_para_horario_comercial(sabado_1225_utc, indice_dispersao=5)
    res_sabado_local = res_sabado + BusinessHoursPolicy.OFFSET_BRASIL
    
    print(f"   • Sábado 12:25 + Jitter 15min -> {res_sabado_local.strftime('%A %d/%m %H:%M:%S')}")
    assert res_sabado_local.weekday() == 0, "Deve ser postergado para Segunda-feira!"
    assert res_sabado_local.time() >= BusinessHoursPolicy._parse_hhmm("08:30"), "Deve ser após 08:30 na Segunda!"

    print("✅ [BLINDAGEM 3 APROVADA]: Jitter jamais vaza mensagens para fora do horário comercial!")


async def test_4_deriva_relogio_e_timestamp_futuro():
    print("\n--- [4/6] Testando Deriva de Relógio e Timestamps no Futuro ---")
    tel = f"{CHAOS_PREFIX}0003"
    async with AsyncSessionLocal() as db:
        lead = await InboundService._obter_ou_criar_lead(db, tel, "Viajante do Tempo")
        lead.controle = models.ControleAtendimento.HUMANO_ASSUMIU
        await db.commit()

        # Insere mensagem humana com timestamp 2 horas NO FUTURO
        futuro_utc = (datetime.now(timezone.utc) + timedelta(hours=2)).replace(tzinfo=None)
        await LeadRepository.add_interaction(db, lead.id, models.InteracaoOrigem.HUMANO, "Mensagem do futuro")
        interacao = await LeadRepository.get_latest_interaction_by_origins(
            db, lead.id, [models.InteracaoOrigem.HUMANO]
        )
        if interacao:
            interacao.criado_em = futuro_utc
            await db.commit()

        retomou = await TransbordoService.verificar_e_executar_retomada_automatica(db, lead)
        print(f"   • Timestamp no futuro -> Auto-retomada retornou: {retomou}")
        assert retomou is False
        print("✅ [BLINDAGEM 4 APROVADA]: Desvio de relógio para o futuro absorvido sem erros.")


async def test_5_webhook_payloads_malformados_e_serializacao():
    print("\n--- [5/6] Testando Payloads Malformados e Serialização no Webhook ---")
    
    # 1. Telefone com valores bizarros
    telefones_estranhos = ["null", "undefined", "+", "++++", " ", "0000000"]
    for t in telefones_estranhos:
        payload = schemas.UazapiPayload(
            chat=schemas.UazapiChat(phone=t),
            message=schemas.UazapiMessage(text="Olá")
        )
        res = await webhook_uazapi(payload)
        assert res["status"] == "ignorado"
    print("   • Telefones bizarros descartados com segurança.")

    # 2. Payload com content como dicionário contendo objetos e subtipos
    payload_complexo = schemas.UazapiPayload(
        chat=schemas.UazapiChat(phone="+558391923098"),  # Telefone na whitelist de sandbox
        message=schemas.UazapiMessage(
            text="Mensagem com dicionário complexo",
            content={"subtipo": "custom", "numero": 123}
        )
    )
    res_complexo = await webhook_uazapi(payload_complexo)
    print(f"   • Payload com content complexo: {res_complexo}")
    assert res_complexo["status"] == "enfileirado_com_debounce"
    print("✅ [BLINDAGEM 5 APROVADA]: Webhook serializa tipos complexos sem crash.")


async def test_6_opt_out_permanente_resistencia_a_mensagens():
    print("\n--- [6/6] Testando Resistência de Opt-out (LGPD) contra Reativação ---")
    tel = f"{CHAOS_PREFIX}0005"
    async with AsyncSessionLocal() as db:
        lead = await InboundService._obter_ou_criar_lead(db, tel, "Cliente Opt-out")
        lead.opt_out = True
        lead.desfecho = models.DesfechoLead.PERDIDO
        await db.commit()

        # O cliente manda mensagem: "Quero preço de energia solar"
        await InboundService._executar_pipeline_atendimento(
            db=db,
            telefone=tel,
            nome_contato="Cliente Opt-out",
            texto_consolidado="Quero preço de energia solar"
        )

        interacoes = await LeadRepository.get_interactions(db, lead.id)
        interacoes_ia = [i for i in interacoes if i.origem == models.InteracaoOrigem.IA]
        assert len(interacoes_ia) == 0, "A IA JAMAIS deve responder a um cliente com opt_out=True!"
        assert lead.opt_out is True
        print("✅ [BLINDAGEM 6 APROVADA]: Opt-out 100% blindado contra reativações acidentais.")


async def main():
    print("=" * 75)
    print("🔥 EXECUTANDO SUÍTE DE CHAOS ENGINEERING, ESTRESSE E VULNERABILIDADES")
    print("=" * 75)
    
    await cleanup_chaos_leads()
    await test_1_race_condition_duplicacao_simultanea()
    await test_2_caracteres_toxicos_e_bytes_nulos()
    await test_3_jitter_e_horario_comercial()
    await test_4_deriva_relogio_e_timestamp_futuro()
    await test_5_webhook_payloads_malformados_e_serializacao()
    await test_6_opt_out_permanente_resistencia_a_mensagens()
    await cleanup_chaos_leads()

    print("\n" + "=" * 75)
    print("🏆 TODAS AS 6 BLINDAGENS DE CHAOS ENGINEERING FORAM APROVADAS COM 100% DE SUCESSO!")
    print("=" * 75)


if __name__ == "__main__":
    asyncio.run(main())
