from contextlib import asynccontextmanager
from fastapi import FastAPI

from core.database import engine, Base
import models 

from api.routers import leads, webhook, testes

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Roda uma única vez ANTES do servidor ligar e aceitar requisições
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title="Ecossistema de Vendas Autônomo API",
    description="Core Backend Refatorado em Clean Architecture",
    version="1.1.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {"message": "API do Ecossistema de Vendas (Refatorada) operante!"}

@app.get("/health", tags=["Sistema"])
async def health_check():
    """
    Endpoint de monitoramento de saúde do sistema.
    Verifica a conectividade ativa com PostgreSQL, Redis e status das chaves de API.
    """
    import os
    from datetime import datetime, timezone
    from sqlalchemy import text
    from core.database import AsyncSessionLocal
    from services.buffer_service import redis_client

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
    saude["componentes"]["uazapi_token"] = bool(os.getenv("UAZAPI_TOKEN"))
    saude["componentes"]["openai_key"] = bool(os.getenv("OPENAI_API_KEY"))

    if not saude["componentes"]["uazapi_token"] or not saude["componentes"]["openai_key"]:
        saude["status"] = "degraded"

    return saude

# Incluindo todos os nossos roteadores ("Gavetas")
app.include_router(leads.router)
app.include_router(webhook.router)
app.include_router(testes.router)
