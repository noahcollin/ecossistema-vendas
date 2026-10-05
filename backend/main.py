import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

import time
from core.logger import logger
from core.database import engine, Base, AsyncSessionLocal
from core.config import settings
from integrations.redis.buffer import redis_client
from integrations.uazapi import close_uazapi_client
from services.followup_service import FollowupService
from services.inbound_service import InboundService

from api.routers import leads, webhook

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Roda uma única vez ANTES do servidor ligar e aceitar requisições
    async with engine.begin() as conn:
        # Schema é governado via migrações Alembic (alembic upgrade head)
        await conn.run_sync(Base.metadata.create_all)

    # Inicia o Motor de Cadência Temporal e Follow-Up em Segundo Plano (RF11 & RF12 do PRD)
    worker_task = asyncio.create_task(FollowupService.worker_loop())

    # 🔄 Recuperação Resiliente de Buffers Órfãos no Redis (Pós-Crash / Pós-Restart)
    async def recuperar_buffers_pendentes():
        try:
            await asyncio.sleep(2.0)  # Aguarda estabilização dos serviços
            chaves = await redis_client.keys("buffer:*")
            if chaves:
                for chave in chaves:
                    telefone = chave.replace("buffer:", "")
                    token = await redis_client.get(f"last_msg_time:{telefone}") or str(time.time_ns())
                    asyncio.create_task(InboundService.processar_debounce(telefone, "Cliente", token))
                    logger.info(f"[RECOVERY STARTUP] 🔄 Recuperado buffer órfão no Redis para {telefone} e iniciado debounce.")
        except Exception as err:
            logger.error(f"[RECOVERY STARTUP ERRO] Falha ao escanear buffers órfãos no Redis: {err}")

    asyncio.create_task(recuperar_buffers_pendentes())

    try:
        yield
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        # Encerramento gracioso de recursos externos e pools de conexão
        try:
            await close_uazapi_client()
        except Exception as err:
            logger.warning(f"[SHUTDOWN] Erro ao encerrar cliente Uazapi: {err}")

        try:
            await redis_client.aclose()
        except Exception as err:
            logger.warning(f"[SHUTDOWN] Erro ao fechar conexão Redis: {err}")

        try:
            await engine.dispose()
        except Exception as err:
            logger.warning(f"[SHUTDOWN] Erro ao liberar pool PostgreSQL: {err}")

app = FastAPI(
    title="Ecossistema de Vendas Autônomo API",
    description="Core Backend Refatorado em Clean Architecture",
    version="1.2.0",
    lifespan=lifespan
)

# Middleware de CORS configurável e seguro para dashboards e frontends (W3C compliant)
cors_origens_raw = (settings.CORS_ORIGINS or "*").strip()
if cors_origens_raw == "*":
    cors_origens = ["*"]
    permitir_credenciais = False
else:
    cors_origens = [o.strip() for o in cors_origens_raw.split(",") if o.strip()]
    permitir_credenciais = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origens,
    allow_credentials=permitir_credenciais,
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

    # 3. Checa Chaves de Serviços Externos e Alertas Operacionais
    saude["componentes"]["uazapi_token"] = bool(settings.UAZAPI_TOKEN)
    saude["componentes"]["openai_key"] = bool(settings.OPENAI_API_KEY)

    try:
        alerta_cota = await redis_client.get("alerta_sistema:openai_sem_creditos")
        if alerta_cota:
            saude["componentes"]["openai_creditos"] = "esgotado"
            saude["alerta_operacional"] = "Créditos da OpenAI esgotados! Leads recebidos foram direcionados ao transbordo humano sem disparos automáticos."
            saude["status"] = "degraded"
        else:
            saude["componentes"]["openai_creditos"] = "operante"
    except Exception:
        pass

    if not saude["componentes"]["uazapi_token"] or not saude["componentes"]["openai_key"]:
        saude["status"] = "degraded"

    # Define HTTP 503 para que balanceadores de carga não enviem tráfego em caso de falha crítica
    if saude["status"] != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return saude

# Incluindo todos os nossos roteadores ("Gavetas")
app.include_router(leads.router)
app.include_router(webhook.router)
