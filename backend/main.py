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

# Incluindo todos os nossos roteadores ("Gavetas")
app.include_router(leads.router)
app.include_router(webhook.router)
app.include_router(testes.router)
