# Ecossistema de Vendas Autônomo - Core Backend

Backend de alta performance projetado sob os princípios de **Clean Architecture**, **Twelve-Factor App** e **Domain-Driven Design (DDD)** para orquestração autônoma de vendas consultivas e qualificação de leads via WhatsApp.

---

## 🏛️ Arquitetura do Sistema

```
backend/
├── agents/             # Especialistas de IA (Vendedor/Closer, Analista, Auditor)
├── api/
│   └── routers/        # Controladores REST HTTP (leads, webhooks)
├── core/               # Núcleo fundacional (config, database, security, logging, metrics)
├── integrations/       # Adaptadores de I/O externo (OpenAI, Uazapi/WhatsApp, Redis)
├── repositories/       # Abstração de persistência (LeadRepository, FollowupRepository)
├── services/           # Regras de negócio puras (Inbound, Lead, Followup, Transbordo)
├── alembic/            # Migrações versionadas do banco PostgreSQL
├── models/             # Entidades relacionais SQLAlchemy 2.0 (lead, interaction, followup, enums)
├── schemas/            # Contratos de dados Pydantic V2 (lead, fsm, auditor, followup, transbordo)
└── main.py             # Ponto de entrada FastAPI com ciclo de vida assíncrono (lifespan)
```

---

## 🚀 Como Executar

### 1. Pré-requisitos
- Docker & Docker Compose
- Chaves de API: OpenAI e Gateway WhatsApp (Uazapi)

### 2. Configuração de Variáveis de Ambiente
Copie o arquivo de exemplo na raiz do projeto:
```bash
cp .env.example .env
```
Preencha suas chaves no `.env` (`OPENAI_API_KEY`, `UAZAPI_TOKEN`, etc.).

### 3. Subir o Ecossistema com Docker
```bash
docker compose up -d --build
```
Os seguintes serviços subirão automaticamente:
- **core-backend** (FastAPI em `http://localhost:8000`)
- **postgres-db** (PostgreSQL 15 em `localhost:5432`)
- **redis-cache** (Redis 7 em `localhost:6379`)

---

## 🧪 Executando Testes

Os testes são executados com `pytest` e divididos em duas suítes:

### Testes Unitários
```bash
docker exec core-backend uv run pytest tests/unit/ -v
```

### Testes de Integração
```bash
docker exec core-backend uv run pytest tests/integration/ -v
```

### Teste Completo da Suíte
```bash
docker exec core-backend uv run pytest -v
```

---

## 🩺 Monitoramento e Health Check

O endpoint `/health` realiza verificações ativas de dependências em tempo de execução:
- Conectividade com PostgreSQL (`SELECT 1`)
- Ping no Redis
- Validação de chaves de provedores externos
- Alerta operacional de exaustão de cota OpenAI

```bash
curl http://localhost:8000/health
```

---

## 🗄️ Migrações de Banco (Alembic)

Para aplicar as migrações mais recentes:
```bash
docker exec core-backend uv run alembic upgrade head
```

Para gerar uma nova migração a partir de alterações no pacote `models/`:
```bash
docker exec core-backend uv run alembic revision --autogenerate -m "descricao_da_migracao"
```
