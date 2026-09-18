"""
MASTER TEST BATTERY RUNNER - ECOSSISTEMA DE VENDAS INTELIGENTTE
==============================================================
Orquestrador central de testes que executa em sequência todas as suítes
especializadas do sistema, gerando um relatório consolidado de integridade:
1. Arquitetura Limpa, Redis Lua Atômico e Concorrência.
2. Blindagem Adversarial, Anti-Loop e Casos de Borda.
3. Máquina de Estados Finita Multidimensional (FSM 4D).
4. Agente Auditor de Negócios e Dossiê Comercial Executivo (JSONB).
5. Estratégia Inbound vs Outbound e Detecção Inteligente de Canais.
6. Resiliência Profunda, Thundering Herd, Unicode e Lead Revival.
"""

import asyncio
import os
import sys
import time
import subprocess

# Ajusta path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SUITES = [
    {
        "id": "1",
        "nome": "Arquitetura Limpa, Redis Lua e Connection Pool",
        "arquivo": "tests/integration/test_clean_architecture_and_concurrency.py"
    },
    {
        "id": "2",
        "nome": "Blindagem Adversarial, Anti-Loop e Edge Cases",
        "arquivo": "tests/integration/test_adversarial_and_stress.py"
    },
    {
        "id": "3",
        "nome": "Máquina de Estados Multidimensional (FSM 4D)",
        "arquivo": "tests/integration/test_multidimensional_fsm.py"
    },
    {
        "id": "4",
        "nome": "Agente Auditor de Negócios e Dossiê Comercial (JSONB)",
        "arquivo": "tests/integration/test_deal_auditor.py"
    },
    {
        "id": "5",
        "nome": "Inbound vs Outbound e Detecção de Canais de Origem",
        "arquivo": "tests/integration/test_inbound_outbound_channel.py"
    },
    {
        "id": "6",
        "nome": "Resiliência Profunda, Thundering Herd e Unicode UTF-8",
        "arquivo": "tests/integration/test_deep_resilience_and_edge_cases.py"
    },
    {
        "id": "7",
        "nome": "Fluxo Abrangente E2E, Desacoplamento de Prompts e API REST",
        "arquivo": "tests/integration/test_battery_comprehensive.py"
    },
    {
        "id": "8",
        "nome": "Segurança de Webhook, FinOps de LLM e Alta Concorrência",
        "arquivo": "tests/integration/test_security_scalability_finops.py"
    }
]

def executar_suites():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    print("=" * 75)
    print("🚀 INICIANDO BATERIA MESTRE DE TESTES DO ECOSSISTEMA DE VENDAS")
    print("=" * 75)
    
    total_suites = len(SUITES)
    aprovadas = 0
    resultados = []
    inicio_total = time.time()

    for idx, suite in enumerate(SUITES, 1):
        print(f"\n[{idx}/{total_suites}] Executando: {suite['nome']}...")
        inicio_suite = time.time()
        caminho_arquivo = os.path.join(root_dir, suite["arquivo"])
        
        proc = subprocess.run(
            [sys.executable, caminho_arquivo],
            cwd=root_dir,
            capture_output=True,
            text=True
        )
        duracao = time.time() - inicio_suite
        sucesso = (proc.returncode == 0)

        if sucesso:
            aprovadas += 1
            status_str = "✅ APROVADO"
        else:
            status_str = "❌ FALHOU"

        resultados.append({
            "id": suite["id"],
            "nome": suite["nome"],
            "sucesso": sucesso,
            "status_str": status_str,
            "duracao": duracao,
            "stdout": proc.stdout,
            "stderr": proc.stderr
        })
        
        print(f"      Status: {status_str} ({duracao:.2f}s)")
        if not sucesso:
            print("      [ERRO DETALHADO]:")
            print(proc.stderr or proc.stdout)

    duracao_total = time.time() - inicio_total

    print("\n" + "=" * 75)
    print("📊 PAINEL CONSOLIDADO DA BATERIA MESTRE DE TESTES")
    print("=" * 75)
    for r in resultados:
        print(f" • [{r['id']}] {r['status_str']} | {r['nome']} ({r['duracao']:.2f}s)")
    
    taxa_sucesso = (aprovadas / total_suites) * 100
    print("-" * 75)
    print(f"🏆 TOTAL DE SUÍTES APROVADAS: {aprovadas}/{total_suites} ({taxa_sucesso:.1f}%)")
    print(f"⏱️ TEMPO TOTAL DE EXECUÇÃO: {duracao_total:.2f}s")
    print("=" * 75 + "\n")

    if aprovadas < total_suites:
        sys.exit(1)

if __name__ == "__main__":
    executar_suites()
