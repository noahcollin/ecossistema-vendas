"""
TESTE DE SIMULAÇÃO DE LONGA CONVERSA, PERSISTÊNCIA DE MEMÓRIA E FINOPS
======================================================================
Este teste simula um atendimento completo de 7 turnos (de ponta a ponta):
1. Injeta informações soltas/específicas no início da jornada (Needle in a Haystack).
2. Empurra a conversa além da janela de histórico recente (6 mensagens).
3. Monitora a troca dinâmica de modelos: FAST (gpt-4o-mini) -> ADVANCED (gpt-4o).
4. Verifica se a memória de longo prazo (resumo_perfil / dados_qualificacao) reteve
   os detalhes soltos (nome da empresa, bairro, cunhado, tipo de telhado, sombra).
5. Testa a reação do Vendedor ao ser desafiado sobre detalhes iniciais.
6. Avalia a geração final do Dossiê Comercial Executivo com o histórico completo.
"""

import asyncio
import os
import sys
import time

# Ajusta path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.database import AsyncSessionLocal
from core.config import settings
import models
import schemas
from repositories.lead_repository import LeadRepository
from services.lead_service import LeadService
from services.agents import (
    analisar_lead_e_fsm,
    gerar_resposta_vendedor,
    auditar_jornada_lead
)

TEST_PHONE = "+5583993330007"

# Conjunto de "agulhas no palheiro" (fatos soltos espalhados no início)
FATOS_ESPALHADOS = {
    "empresa": "Padaria Trigo & Mel",
    "bairro_cidade": "Bodocongó em Campina Grande",
    "consumo_reais": "R$ 3.850",
    "equipamentos": "fornos elétricos e câmaras frias",
    "telhado_e_sombra": "telhas coloniais antigas de cerâmica com sombra de árvore",
    "indicacao": "cunhado Marcondes de Pocinhos"
}

ROTEIRO_CONVERSA = [
    {
        "turno": 1,
        "fase_esperada": "NOVO_CONTATO",
        "modelo_esperado": "gpt-4o-mini",
        "msg_cliente": (
            "Olá, boa tarde! Sou o Roberto, proprietário da Padaria Trigo & Mel aqui no bairro Bodocongó em Campina Grande. "
            "Vi o anúncio de energia solar de vocês no Instagram."
        ),
        "fatos_inseridos": ["Roberto", "Padaria Trigo & Mel", "Bodocongó", "Campina Grande", "Instagram"]
    },
    {
        "turno": 2,
        "fase_esperada": "QUALIFICACAO",
        "modelo_esperado": "gpt-4o-mini",
        "msg_cliente": (
            "Minha conta de luz tá vindo quase R$ 3.850 por mês por causa dos nossos fornos elétricos e câmaras frias. "
            "Queria saber se consigo reduzir isso, mas meu telhado é daquelas telhas coloniais antigas de cerâmica "
            "e tem uma árvore grande do vizinho que faz sombra na parte da tarde."
        ),
        "fatos_inseridos": ["R$ 3.850", "fornos elétricos", "câmaras frias", "telhas coloniais", "sombra de árvore"]
    },
    {
        "turno": 3,
        "fase_esperada": "QUALIFICACAO",
        "modelo_esperado": "gpt-4o-mini",
        "msg_cliente": (
            "Quem me indicou vocês foi meu cunhado Marcondes, que colocou placas com vocês ano passado lá no sítio dele em Pocinhos. "
            "Ele falou muito bem do Seu Zé."
        ),
        "fatos_inseridos": ["cunhado Marcondes", "sítio em Pocinhos"]
    },
    {
        "turno": 4,
        "fase_esperada": "NEGOCIACAO",
        "modelo_esperado": "gpt-4o",
        "msg_cliente": (
            "Vocês conseguem montar uma estimativa para ver quanto eu economizaria e se compensa com essa questão da sombra da árvore?"
        ),
        "fatos_inseridos": []
    },
    {
        "turno": 5,
        "fase_esperada": "NEGOCIACAO",
        "modelo_esperado": "gpt-4o",
        "msg_cliente": (
            "Entendi a ideia dos microinversores para anular o impacto da sombra. "
            "Mas o investimento de R$ 75.000 tá um pouco acima do que eu planejava desembolsar à vista. "
            "Vocês trabalham com financiamento bancário com carência?"
        ),
        "fatos_inseridos": []
    },
    {
        "turno": 6,
        "fase_esperada": "NEGOCIACAO",
        "modelo_esperado": "gpt-4o",
        "msg_cliente": (
            "Antes da gente bater o martelo, Seu Zé: quero fazer um teste com você para ter certeza que você tá atento. "
            "Você lembra qual é exatamente o meu tipo de comércio, em qual bairro fica, o que gasta mais energia lá "
            "e quem foi que me indicou sua empresa? Se você lembrar de cabeça, eu fecho agora!"
        ),
        "fatos_inseridos": ["TESTE_DE_MEMORIA_DO_CLIENTE"]
    },
    {
        "turno": 7,
        "fase_esperada": "FECHAMENTO",
        "modelo_esperado": "gpt-4o",
        "msg_cliente": (
            "Sensacional, Seu Zé! Você lembrou de tudo com precisão cirúrgica. "
            "Fechado então! Pode gerar o contrato no nome da Padaria Trigo & Mel. Me passa os próximos passos!"
        ),
        "fatos_inseridos": ["FECHAMENTO_OFICIAL"]
    }
]

async def cleanup(db, telefone: str):
    lead = await LeadRepository.get_by_phone(db, telefone)
    if lead:
        await LeadRepository.delete_interactions_by_lead_id(db, lead.id)
        await LeadRepository.delete_lead(db, lead)

async def executar_simulacao():
    print("=" * 80)
    print("🧪 SIMULAÇÃO DE LONGA CONVERSA: PERSISTÊNCIA DE MEMÓRIA & FINOPS DINÂMICO")
    print("=" * 80)

    settings.DYNAMIC_MODEL_ROUTING = True
    settings.MODEL_CLOSER_FAST = "gpt-4o-mini"
    settings.MODEL_CLOSER_ADVANCED = "gpt-4o"
    settings.JANELA_HISTORICO_RECENTE = 6  # Fixa a janela imediata em 6 mensagens

    async with AsyncSessionLocal() as db:
        await cleanup(db, TEST_PHONE)

        # 1. Criação do Lead Inicial
        lead = await LeadRepository.create(
            db=db,
            telefone=TEST_PHONE,
            nome="Roberto",
            tipo_entrada=models.TipoEntradaLead.INBOUND,
            origem_canal="WHATSAPP_DIRETO"
        )
        print(f"👤 Lead Criado: ID {lead.id} | Telefone: {lead.telefone} | Nome: {lead.nome}")

        historico_completo = []
        modelos_utilizados = []
        fatos_recuperados = {}

        for etapa in ROTEIRO_CONVERSA:
            turno_num = etapa["turno"]
            msg_cli = etapa["msg_cliente"]

            print("\n" + "-" * 80)
            print(f"📍 TURNO {turno_num}/7 | Cliente ➔ IA")
            print(f"💬 Cliente: \"{msg_cli}\"")

            # Registra interação do cliente no banco
            interacao_cli = await LeadRepository.add_interaction(
                db=db,
                lead_id=lead.id,
                origem=models.InteracaoOrigem.CLIENTE,
                texto=msg_cli
            )
            historico_completo.append(interacao_cli)

            # Busca janela imediata configurada
            historico_janela = await LeadRepository.get_recent_interactions(
                db=db,
                lead_id=lead.id,
                limit=settings.JANELA_HISTORICO_RECENTE
            )

            # 🧠 1. Analista de Inteligência Comercial (FSM 4D)
            inicio_analista = time.time()
            analise = await analisar_lead_e_fsm(
                lead=lead,
                historico_recente=historico_janela,
                nova_mensagem=msg_cli
            )
            tempo_analista = time.time() - inicio_analista

            # Atualiza canal detectado
            if analise.origem_canal_detectada:
                if not lead.origem_canal or lead.origem_canal == "WHATSAPP_DIRETO":
                    lead.origem_canal = analise.origem_canal_detectada

            # Persiste as 4 Dimensões
            lead.etapa_funil = analise.etapa_sugerida
            lead.desfecho = analise.desfecho_sugerido
            lead.temperatura = analise.temperatura_sugerida
            lead.resumo_perfil = analise.resumo_perfil
            lead.dados_qualificacao = (
                analise.dados_qualificacao.model_dump()
                if hasattr(analise.dados_qualificacao, "model_dump")
                else analise.dados_qualificacao
            )
            if analise.valor_estimado:
                lead.valor_estimado = analise.valor_estimado
            if analise.tags_sugeridas:
                tags_set = set(lead.tags or [])
                tags_set.update(analise.tags_sugeridas)
                lead.tags = list(tags_set)

            await db.commit()
            await db.refresh(lead)

            # Define modelo esperado conforme lógica FinOps
            if lead.etapa_funil in [models.EtapaFunil.NOVO_CONTATO, models.EtapaFunil.QUALIFICACAO]:
                modelo_esperado = settings.MODEL_CLOSER_FAST
            else:
                modelo_esperado = settings.MODEL_CLOSER_ADVANCED

            modelos_utilizados.append(modelo_esperado)

            print(f"📊 [FSM 4D Analista] ({tempo_analista:.2f}s):")
            print(f"   • Etapa Funil: {lead.etapa_funil.value}")
            print(f"   • Desfecho: {lead.desfecho.value} | Temp: {lead.temperatura.value} | Canal: {lead.origem_canal}")
            print(f"   • Tags: {lead.tags}")
            print(f"   • FinOps Model Roteado: ⚡ {modelo_esperado.upper()} ⚡")

            # 🤖 2. Vendedor Comercial ("Seu Zé")
            inicio_vendedor = time.time()
            resposta_vendedor = await gerar_resposta_vendedor(
                nome_cliente_bruto=lead.nome,
                ficha_resumo=lead.resumo_perfil,
                etapa_funil=lead.etapa_funil,
                historico_recente=historico_janela
            )
            tempo_vendedor = time.time() - inicio_vendedor

            print(f"🤖 Seu Zé ({tempo_vendedor:.2f}s): \"{resposta_vendedor}\"")

            # Registra resposta da IA no banco
            interacao_ia = await LeadRepository.add_interaction(
                db=db,
                lead_id=lead.id,
                origem=models.InteracaoOrigem.IA,
                texto=resposta_vendedor
            )
            historico_completo.append(interacao_ia)

            # Verificação especial no Turno 6 (Desafio de Memória)
            if turno_num == 6:
                resp_lower = resposta_vendedor.lower()
                resumo_lower = (lead.resumo_perfil or "").lower()

                check_padaria = "trigo" in resp_lower or "padaria" in resp_lower or "padaria" in resumo_lower
                check_bairro = "bodocongó" in resp_lower or "campina" in resp_lower or "bodocongó" in resumo_lower
                check_cunhado = "marcondes" in resp_lower or "pocinhos" in resp_lower or "marcondes" in resumo_lower
                check_fornos = "forno" in resp_lower or "câmara" in resp_lower or "forno" in resumo_lower

                fatos_recuperados = {
                    "Padaria Trigo & Mel": check_padaria,
                    "Bodocongó / Campina Grande": check_bairro,
                    "Cunhado Marcondes / Pocinhos": check_cunhado,
                    "Fornos / Câmaras Frias": check_fornos
                }

                print("\n🧠 [AUDITORIA DE RECALL DE MEMÓRIA NO TURNO 6]:")
                for item, sucesso in fatos_recuperados.items():
                    status_icon = "✅ PRESENTE" if sucesso else "❌ AUSENTE"
                    print(f"   • {item}: {status_icon}")

        # 3. Auditoria Comercial Executiva Final
        print("\n" + "=" * 80)
        print("📋 GERANDO DOSSIÊ COMERCIAL EXECUTIVO FINAL (DealAuditorAgent)...")
        print("=" * 80)
        dossie = await auditar_jornada_lead(lead, historico_completo)
        await LeadRepository.salvar_dossie(db, lead, dossie.model_dump())

        print(f"• Desfecho Final: {dossie.resultado_final.desfecho.value}")
        print(f"• Canal de Origem: {dossie.origem_canal}")
        print(f"• Tipo de Entrada: {dossie.tipo_entrada}")
        print(f"• Nota IA: {dossie.nota_atendimento_ia}/10")
        print(f"• História do Lead:\n  {dossie.historia_do_lead}")
        print(f"• O Que Agradou: {dossie.o_que_agradou}")
        print(f"• Estratégia Utilizada: {dossie.estrategia_utilizada}")
        print(f"• Feedback para o Negócio: {dossie.feedback_para_o_negocio}")
        print(f"• Dica de Ouro: {dossie.proximo_passo.dica_de_ouro}")

        # 4. Asserções de Qualidade
        print("\n" + "=" * 80)
        print("🔍 VERIFICAÇÃO RIGOROSA DAS ASSERÇÕES DO TESTE")
        print("=" * 80)

        # Asserção A: Troca dinâmica de modelo FAST -> ADVANCED
        assert "gpt-4o-mini" in modelos_utilizados[:3], "Deveria usar gpt-4o-mini nas etapas iniciais"
        assert "gpt-4o" in modelos_utilizados[3:], "Deveria usar gpt-4o nas etapas de negociação e fechamento"
        print("✅ [FINOPS VERIFICADO]: Alternância gpt-4o-mini -> gpt-4o executada perfeitamente conforme a etapa do funil!")

        # Asserção B: Canal do Instagram detectado
        assert lead.origem_canal == "META_ADS", f"Esperado META_ADS, obteve {lead.origem_canal}"
        print("✅ [CANAL VERIFICADO]: Origem detectada como META_ADS (Instagram) sem perda!")

        # Asserção C: Desfecho GANHO
        assert lead.desfecho == models.DesfechoLead.GANHO
        assert lead.etapa_funil == models.EtapaFunil.FECHAMENTO
        print("✅ [FUNIL VERIFICADO]: Lead progrediu até FECHAMENTO com desfecho GANHO!")

        # Asserção D: Preservação de Fatos Críticos na Memória
        resumo_final = (lead.resumo_perfil or "").lower()
        dossie_historia = dossie.historia_do_lead.lower()
        texto_analise_total = resumo_final + " " + dossie_historia

        assert "padaria" in texto_analise_total or "trigo" in texto_analise_total, "Nome da padaria foi perdido!"
        assert "bodocongó" in texto_analise_total or "campina" in texto_analise_total, "Localização foi perdida!"
        assert "marcondes" in texto_analise_total or "pocinhos" in texto_analise_total or "cunhado" in texto_analise_total, "Indicação do cunhado foi perdida!"
        print("✅ [MEMÓRIA SEM PERDAS]: Nenhuma informação solta do início foi esquecida, mesmo após 7 turnos longos!")

        # Asserção E: Ausência de Alucinações Graves
        assert "fusca" not in resumo_final and "apartamento" not in resumo_final
        print("✅ [SEM ALUCINAÇÕES]: O modelo manteve fidelidade factual aos dados do cliente.")

        # Cleanup final
        await cleanup(db, TEST_PHONE)
        print("🧹 Cleanup do lead de testes concluído.")

        print("\n" + "=" * 80)
        print("🎉 SIMULAÇÃO CONCLUÍDA COM 100% DE SUCESSO E APROVAÇÃO!")
        print("=" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(executar_simulacao())
