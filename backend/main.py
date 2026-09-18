from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from core.database import engine, Base, AsyncSessionLocal
from core.config import settings
from services.buffer_service import redis_client
import models 

from api.routers import leads, webhook, testes

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Roda uma única vez ANTES do servidor ligar e aceitar requisições
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Migração idempotente para garantir novas colunas em tabelas existentes
        await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS resumo_perfil TEXT;"))
        await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS dados_qualificacao JSONB;"))
        await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS etapa_funil VARCHAR(50) DEFAULT 'NOVO_CONTATO';"))
        await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS desfecho VARCHAR(50) DEFAULT 'EM_ANDAMENTO';"))
        await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS controle VARCHAR(50) DEFAULT 'PILOTO_IA';"))
        await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS temperatura VARCHAR(20) DEFAULT 'FRIO';"))
        await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS motivo_perda VARCHAR(255);"))
        await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS valor_estimado DOUBLE PRECISION;"))
        await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb;"))
        await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS opt_out BOOLEAN DEFAULT FALSE;"))
        await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS dossie_comercial JSONB;"))
        await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS tipo_entrada VARCHAR(50) DEFAULT 'INBOUND';"))
        await conn.execute(text("ALTER TABLE leads ADD COLUMN IF NOT EXISTS origem_canal VARCHAR(100) DEFAULT 'WHATSAPP_DIRETO';"))
    yield

app = FastAPI(
    title="Ecossistema de Vendas Autônomo API",
    description="Core Backend Refatorado em Clean Architecture",
    version="1.2.0",
    lifespan=lifespan
)

# Middleware de CORS para permitir integração com dashboards e frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "API do Ecossistema de Vendas (Refatorada) operante!"}

@app.get("/health", tags=["Sistema"])
async def health_check(response: Response):
    """
    Endpoint de monitoramento de saúde do sistema.
    Verifica a conectividade ativa com PostgreSQL, Redis e status das chaves de API.
    Retorna HTTP 200 se saudável ou HTTP 503 se dependências vitais falharem.
    """
    saude = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "componentes": {}
    }

    # 1. Checa PostgreSQL
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT 1"))
            saude["componentes"]["postgres"] = "conectado" if res.scalar() == 1 else "erro"
    except Exception as e:
        saude["componentes"]["postgres"] = f"erro: {str(e)}"
        saude["status"] = "degraded"

    # 2. Checa Redis
    try:
        pong = await redis_client.ping()
        saude["componentes"]["redis"] = "conectado" if pong else "erro"
    except Exception as e:
        saude["componentes"]["redis"] = f"erro: {str(e)}"
        saude["status"] = "degraded"

    # 3. Checa Chaves de Serviços Externos
    saude["componentes"]["uazapi_token"] = bool(settings.UAZAPI_TOKEN)
    saude["componentes"]["openai_key"] = bool(settings.OPENAI_API_KEY)

    if not saude["componentes"]["uazapi_token"] or not saude["componentes"]["openai_key"]:
        saude["status"] = "degraded"

    # Define HTTP 503 para que balanceadores de carga não enviem tráfego em caso de falha crítica
    if saude["status"] != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return saude

# Incluindo todos os nossos roteadores ("Gavetas")
app.include_router(leads.router)
app.include_router(webhook.router)
app.include_router(testes.router)
