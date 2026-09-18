# 🧪 Arquitetura de Testes & Qualidade de Software

Este diretório centraliza todas as suítes de testes automatizados, simulações de alta concorrência e ferramentas de auditoria comercial do **Ecossistema de Vendas Autônomo**.

---

## 📂 Estrutura de Diretórios

```text
backend/tests/
│
├── run_master_test_battery.py     # 🚀 Orquestrador Mestre (Executa todas as 8 suítes)
├── README.md                      # 📖 Este guia de documentação e arquitetura
│
├── integration/                   # 🧩 Suítes de Integração (Banco, Redis, FSM, Agentes)
│   ├── test_clean_architecture_and_concurrency.py  # [Suíte 1] Repositório, Serviço e Lua Atômico
│   ├── test_adversarial_and_stress.py              # [Suíte 2] Injeções maliciosas, loops e spam
│   ├── test_multidimensional_fsm.py                # [Suíte 3] FSM 4D (Etapa, Desfecho, Controle, Temp)
│   ├── test_deal_auditor.py                        # [Suíte 4] Dossiê Comercial Executivo em JSONB
│   ├── test_inbound_outbound_channel.py            # [Suíte 5] Inbound vs Outbound e canais de captação
│   ├── test_deep_resilience_and_edge_cases.py      # [Suíte 6] Thundering Herd, Unicode e Lead Revival
│   ├── test_battery_comprehensive.py               # [Suíte 7] Ciclo comercial completo E2E e API REST
│   └── test_security_scalability_finops.py         # [Suíte 8] Auth de Webhook, Pool 75 e FinOps Fast/Adv
│
├── e2e/                           # 🎭 Simulações de Ponta a Ponta de Longa Duração
│   └── test_long_conversation_memory_and_finops.py # Simulação real de 7 turnos com recall de memória
│
├── scripts/                       # 🛠️ Utilitários, Demos e Diagnósticos
│   ├── demo_visualizacao_saidas.py                 # Demonstração visual formatada das saídas
│   ├── verify_db_schema.py                         # Diagnóstico de integridade do PostgreSQL
│   └── output_visualizacao.json                    # Snapshot de dados do dossiê comercial
│
└── legacy/                        # 📦 Histórico / Testes Intermediários Anteriores
    ├── test_refactoring_and_reset.py               # Validação pontual da fase 1 de refatoração
    ├── test_multi_agent_fsm.py                     # Validação intermediária da FSM inicial
    └── test_live_validation_e2e.py                 # Validação exploratória inicial
```

---

## 🚀 Como Executar os Testes

### 1. Executar a Bateria Mestre Completa (Recomendado)
Executa em sequência todas as 8 suítes oficiais e gera o painel consolidado:
```bash
docker exec core-backend uv run python tests/run_master_test_battery.py
```

### 2. Executar uma Suíte Específica de Integração
```bash
docker exec core-backend uv run python tests/integration/test_security_scalability_finops.py
```

### 3. Executar a Simulação de Longa Conversa (E2E)
Testa a retenção de memória após 7 turnos e a alternância dinâmica de modelos (`gpt-4o-mini` -> `gpt-4o`):
```bash
docker exec core-backend uv run python tests/e2e/test_long_conversation_memory_and_finops.py
```

### 4. Executar o Script de Demonstração Visual
Gera o relatório visual de todas as inteligências ativas:
```bash
docker exec core-backend uv run python tests/scripts/demo_visualizacao_saidas.py
```
