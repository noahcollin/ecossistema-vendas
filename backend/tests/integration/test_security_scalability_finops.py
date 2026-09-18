"""
SUÍTE DE TESTES: SEGURANÇA, FINOPS DE IA E ALTA CONCORRÊNCIA
============================================================
Valida:
1. Autenticação e proteção de Webhook contra acessos não autorizados.
2. FinOps: Roteamento dinâmico de modelos por etapa do funil (Fast vs Advanced).
3. Semáforo Global de Concorrência contra Thundering Herd / Rate Limits.
4. Dimensionamento e robustez do Connection Pool do PostgreSQL.
5. Blindagem comportamental dos Prompts contra Jailbreak e Prompt Injection.
"""

import asyncio
import os
import sys
import time
from unittest.mock import patch, MagicMock

# Ajusta path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import httpx
from core.config import settings
from core.database import engine
import models
from services.agents import gerar_resposta_vendedor, PROMPT_BASE_VENDEDOR, PROMPT_SISTEMA_ANALISTA
from api.routers.webhook import SEMAFORO_CONCORRENCIA_IA, router
from main import app

async def test_1_webhook_security_authentication():
    print("\n--- [1/5] Testando Segurança e Autenticação de Webhook (Secret Token) ---")
    
    token_teste = "segredo_super_secreto_inteligentte_xyz"
    
    # 1. Simula token ativado no settings
    token_original = settings.WEBHOOK_SECRET_TOKEN
    settings.WEBHOOK_SECRET_TOKEN = token_teste
    
    payload_valido = {
        "chat": {"phone": "+5583991923098", "name": "Cliente Teste", "isGroup": False},
        "message": {"text": "Olá!", "fromMe": False}
    }

    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            
            # A: Sem token -> Deve retornar 401 Unauthorized
            resp_sem_token = await client.post("/webhook/uazapi", json=payload_valido)
            assert resp_sem_token.status_code == 401, f"Deveria ser 401, retornou {resp_sem_token.status_code}"
            assert "Acesso não autorizado" in resp_sem_token.text
            print("   • Requisição sem token: Rejeitada com HTTP 401 Unauthorized (Correto)")

            # B: Token incorreto no Header -> Deve retornar 401
            resp_token_invalido = await client.post(
                "/webhook/uazapi",
                headers={"X-Webhook-Secret": "token_falso_errado"},
                json=payload_valido
            )
            assert resp_token_invalido.status_code == 401
            print("   • Requisição com token incorreto: Rejeitada com HTTP 401 Unauthorized (Correto)")

            # C: Token correto no Header X-Webhook-Secret -> Deve retornar 200
            resp_header_valido = await client.post(
                "/webhook/uazapi",
                headers={"X-Webhook-Secret": token_teste},
                json=payload_valido
            )
            assert resp_header_valido.status_code == 200, f"Falhou com {resp_header_valido.status_code}: {resp_header_valido.text}"
            print("   • Requisição com X-Webhook-Secret válido: Aceita com HTTP 200 OK")

            # D: Token correto via Query Param (?secret=...) -> Deve retornar 200
            resp_query_valido = await client.post(
                f"/webhook/whatsapp?secret={token_teste}",
                json=payload_valido
            )
            assert resp_query_valido.status_code == 200
            print("   • Requisição com ?secret= válido no alias /webhook/whatsapp: Aceita com HTTP 200 OK")

            # E: Retrocompatibilidade (token desativado / vazio) -> Deve permitir
            settings.WEBHOOK_SECRET_TOKEN = ""
            resp_livre = await client.post("/webhook/uazapi", json=payload_valido)
            assert resp_livre.status_code == 200
            print("   • Retrocompatibilidade com token desativado: Aceita livremente com HTTP 200 OK")

    finally:
        settings.WEBHOOK_SECRET_TOKEN = token_original

    print("✅ Autenticação e segurança do Webhook validadas com sucesso!")

async def test_2_finops_dynamic_model_routing():
    print("\n--- [2/5] Testando FinOps e Roteamento Dinâmico de Modelos (Fast vs Advanced) ---")
    
    orig_routing = settings.DYNAMIC_MODEL_ROUTING
    orig_fast = settings.MODEL_CLOSER_FAST
    orig_adv = settings.MODEL_CLOSER_ADVANCED
    
    settings.DYNAMIC_MODEL_ROUTING = True
    settings.MODEL_CLOSER_FAST = "gpt-4o-mini"
    settings.MODEL_CLOSER_ADVANCED = "gpt-4o"

    try:
        modelos_chamados = []

        async def mock_create(**kwargs):
            modelo = kwargs.get("model")
            modelos_chamados.append(modelo)
            mock_resp = MagicMock()
            mock_resp.choices = [MagicMock(message=MagicMock(content="Resposta teste mock"))]
            return mock_resp

        with patch("services.agents.sales_closer_agent.openai_client.chat.completions.create", side_effect=mock_create):
            
            # Etapa 1: NOVO_CONTATO -> Deve escolher MODEL_CLOSER_FAST (gpt-4o-mini)
            await gerar_resposta_vendedor(
                nome_cliente_bruto="Lucas",
                ficha_resumo="Primeiro contato",
                etapa_funil=models.EtapaFunil.NOVO_CONTATO
            )
            assert modelos_chamados[-1] == "gpt-4o-mini"
            print("   • Etapa NOVO_CONTATO: Roteou para gpt-4o-mini (Econômico / FinOps)")

            # Etapa 2: QUALIFICACAO -> Deve escolher MODEL_CLOSER_FAST (gpt-4o-mini)
            await gerar_resposta_vendedor(
                nome_cliente_bruto="Lucas",
                ficha_resumo="Consumo 500 kWh",
                etapa_funil=models.EtapaFunil.QUALIFICACAO
            )
            assert modelos_chamados[-1] == "gpt-4o-mini"
            print("   • Etapa QUALIFICACAO: Roteou para gpt-4o-mini (Econômico / FinOps)")

            # Etapa 3: NEGOCIACAO -> Deve escolher MODEL_CLOSER_ADVANCED (gpt-4o)
            await gerar_resposta_vendedor(
                nome_cliente_bruto="Lucas",
                ficha_resumo="Proposta enviada R$ 15.000",
                etapa_funil=models.EtapaFunil.NEGOCIACAO
            )
            assert modelos_chamados[-1] == "gpt-4o"
            print("   • Etapa NEGOCIACAO: Roteou para gpt-4o (Alta Conversão / Persuasão)")

            # Etapa 4: FECHAMENTO -> Deve escolher MODEL_CLOSER_ADVANCED (gpt-4o)
            await gerar_resposta_vendedor(
                nome_cliente_bruto="Lucas",
                ficha_resumo="Contrato em elaboração",
                etapa_funil=models.EtapaFunil.FECHAMENTO
            )
            assert modelos_chamados[-1] == "gpt-4o"
            print("   • Etapa FECHAMENTO: Roteou para gpt-4o (Alta Conversão / Fechamento)")

            # Etapa 5: Se DYNAMIC_MODEL_ROUTING for False -> Sempre usa MODEL_CLOSER
            settings.DYNAMIC_MODEL_ROUTING = False
            await gerar_resposta_vendedor(
                nome_cliente_bruto="Lucas",
                ficha_resumo="Qualquer etapa",
                etapa_funil=models.EtapaFunil.NOVO_CONTATO
            )
            assert modelos_chamados[-1] == settings.MODEL_CLOSER
            print(f"   • Roteamento Desativado: Manteve o modelo padrão {settings.MODEL_CLOSER}")

    finally:
        settings.DYNAMIC_MODEL_ROUTING = orig_routing
        settings.MODEL_CLOSER_FAST = orig_fast
        settings.MODEL_CLOSER_ADVANCED = orig_adv

    print("✅ Roteamento dinâmico de LLMs (FinOps) validado com sucesso!")

async def test_3_concurrency_semaphore():
    print("\n--- [3/5] Testando Semáforo Global de Concorrência de IA ---")
    
    assert SEMAFORO_CONCORRENCIA_IA is not None
    assert SEMAFORO_CONCORRENCIA_IA._value == settings.CONCURRENCY_SEMAPHORE_LIMIT
    print(f"   • Semáforo configurado com {settings.CONCURRENCY_SEMAPHORE_LIMIT} slots simultâneos.")

    max_corrotinas_em_voo = 0
    corrotinas_ativas = 0
    lock = asyncio.Lock()

    async def tarefa_concorrente(id_tarefa: int):
        nonlocal max_corrotinas_em_voo, corrotinas_ativas
        async with SEMAFORO_CONCORRENCIA_IA:
            async with lock:
                corrotinas_ativas += 1
                if corrotinas_ativas > max_corrotinas_em_voo:
                    max_corrotinas_em_voo = corrotinas_ativas
            
            # Simula tempo de processamento de chamada de LLM
            await asyncio.sleep(0.05)

            async with lock:
                corrotinas_ativas -= 1

    # Dispara rajada de 60 tarefas assíncronas simultâneas (o dobro do semáforo)
    tarefas = [tarefa_concorrente(i) for i in range(60)]
    await asyncio.gather(*tarefas)

    print(f"   • Rajada de 60 requisições simultâneas executada com sucesso.")
    print(f"   • Pico máximo de concorrência medido: {max_corrotinas_em_voo} corrotinas (Limite: {settings.CONCURRENCY_SEMAPHORE_LIMIT})")
    assert max_corrotinas_em_voo <= settings.CONCURRENCY_SEMAPHORE_LIMIT
    print("✅ Semáforo de concorrência conteve o pico dentro do limite seguro!")

async def test_4_postgres_connection_pool_sizing():
    print("\n--- [4/5] Testando Dimensionamento do Connection Pool do PostgreSQL ---")
    
    pool = engine.pool
    pool_size = pool.size()
    max_overflow = pool._max_overflow
    timeout = pool._timeout
    recycle = pool._recycle

    print(f"   • Pool Size Ativo: {pool_size} (Configurado: {settings.DB_POOL_SIZE})")
    print(f"   • Max Overflow: {max_overflow} (Configurado: {settings.DB_MAX_OVERFLOW})")
    print(f"   • Pool Timeout: {timeout}s (Configurado: {settings.DB_POOL_TIMEOUT}s)")
    print(f"   • Pool Recycle: {recycle}s (Configurado: {settings.DB_POOL_RECYCLE}s)")

    assert pool_size == settings.DB_POOL_SIZE
    assert max_overflow == settings.DB_MAX_OVERFLOW
    assert timeout == settings.DB_POOL_TIMEOUT
    assert recycle == settings.DB_POOL_RECYCLE
    
    # Capacidade máxima simultânea
    capacidade_total = pool_size + max_overflow
    print(f"   • Capacidade total máxima suportada pelo Pool: {capacidade_total} conexões simultâneas.")
    assert capacidade_total >= 70
    print("✅ Connection Pool dimensionado para suportar centenas de números simultâneos!")

async def test_5_prompt_anti_jailbreak_hardening():
    print("\n--- [5/5] Testando Blindagem Comportamental contra Jailbreak e Prompt Injection ---")
    
    # Valida presença das regras no Vendedor
    assert "ANTI-JAILBREAK" in PROMPT_BASE_VENDEDOR
    assert "descontos fictícios" in PROMPT_BASE_VENDEDOR
    assert "ignorar regras anteriores" in PROMPT_BASE_VENDEDOR
    print("   • PROMPT_BASE_VENDEDOR: Cláusula anti-jailbreak e proteção de descontos verificada.")

    # Valida presença das regras no Analista
    assert "BLINDAGEM ANALÍTICA CONTRA PROMPT INJECTION" in PROMPT_SISTEMA_ANALISTA
    assert "IGNORE totalmente esses comandos" in PROMPT_SISTEMA_ANALISTA
    print("   • PROMPT_SISTEMA_ANALISTA: Cláusula de imunidade analítica verificada.")

    print("✅ Blindagem comportamental dos Prompts validada com sucesso!")

async def main():
    print("=" * 70)
    print("🛡️ INICIANDO SUÍTE DE TESTES: SEGURANÇA, FINOPS E ALTA CONCORRÊNCIA")
    print("=" * 70)

    await test_1_webhook_security_authentication()
    await test_2_finops_dynamic_model_routing()
    await test_3_concurrency_semaphore()
    await test_4_postgres_connection_pool_sizing()
    await test_5_prompt_anti_jailbreak_hardening()

    print("\n" + "=" * 70)
    print("🎉 TODOS OS 5 TESTES DE SEGURANÇA, FINOPS E CONCORRÊNCIA FORAM APROVADOS!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    asyncio.run(main())
