import asyncio
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from core.background import spawn_background_task, drain_background_tasks, get_active_background_tasks_count
from core.config import settings
from core.database import engine, Base, AsyncSessionLocal
from core.exceptions import (
    AppException,
    LeadNotFoundError,
    InvalidPhoneNumberError,
    LeadOptedOutError,
    TransbordoStateError,
    SecurityException,
)
from core.logger import logger
from core.security import SecurityHeadersMiddleware
from integrations.redis.buffer import redis_client
from integrations.redis.gateway import default_redis_buffer_gateway
from integrations.uazapi import close_uazapi_client
from services.cadence import FollowupService
from services.inbound import InboundService, SendEventService
from services.settings import SettingsService

from api.routers import leads, webhook, analytics, settings as settings_router, auth as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Aquecimento resiliente do cache L1 de configurações operacionais
    try:
        async with AsyncSessionLocal() as session:
            await SettingsService.obter_configuracoes(session)
    except Exception as cfg_err:
        logger.warning(f"[STARTUP SETTINGS] ⚠️ Aquecimento inicial com defaults em memória: {cfg_err}")

    worker_task = asyncio.create_task(FollowupService.worker_loop(), name="followup_worker_loop")
    send_poller_task = asyncio.create_task(SendEventService.worker_loop(), name="send_poller_worker_loop")

    async def recuperar_buffers_pendentes() -> None:
        try:
            await asyncio.sleep(2.0)
            telefones = await default_redis_buffer_gateway.listar_telefones_com_buffer()
            for telefone in telefones:
                token = await redis_client.get(f"last_msg_time:{telefone}") or str(time.time_ns())
                spawn_background_task(
                    InboundService.processar_debounce(telefone, "Cliente", token),
                    name=f"recovery_debounce_{telefone}",
                )
                logger.info(
                    f"[RECOVERY STARTUP] 🔄 Recuperado buffer órfão via SCAN para {telefone} e iniciado debounce."
                )
        except Exception as err:
            logger.error(f"[RECOVERY STARTUP ERRO] Falha ao escanear buffers órfãos no Redis: {err}")

    spawn_background_task(recuperar_buffers_pendentes(), name="startup_buffer_recovery")

    try:
        yield
    finally:
        worker_task.cancel()
        send_poller_task.cancel()
        for t in (worker_task, send_poller_task):
            try:
                await t
            except asyncio.CancelledError:
                pass

        await drain_background_tasks(timeout=5.0)

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


_em_producao = settings.ENVIRONMENT.strip().lower() == "production"

app = FastAPI(
    title="Ecossistema de Vendas Autônomo API",
    description="Core Backend em Clean Architecture — Governança Comercial & Agentes Cognitivos",
    version="1.3.0",
    lifespan=lifespan,
    docs_url=None if _em_producao else "/docs",
    redoc_url=None if _em_producao else "/redoc",
    openapi_url=None if _em_producao else "/openapi.json",
)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Traduz exceções puras de Domínio/Infraestrutura em respostas HTTP padronizadas na borda Web."""
    if isinstance(exc, LeadNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, (InvalidPhoneNumberError, LeadOptedOutError, TransbordoStateError)):
        code = status.HTTP_400_BAD_REQUEST
    elif isinstance(exc, SecurityException):
        code = status.HTTP_401_UNAUTHORIZED
    else:
        code = status.HTTP_500_INTERNAL_SERVER_ERROR

    return JSONResponse(
        status_code=code,
        content={"detail": exc.message, "details": exc.details},
    )


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

app.add_middleware(SecurityHeadersMiddleware)


@app.get("/")
async def root():
    return {"message": "API do Ecossistema de Vendas (Refatorada) operante!"}


@app.get("/health", tags=["Sistema"])
async def health_check(response: Response):
    """
    Endpoint de monitoramento de saúde e telemetria operacional do ecossistema.
    Verifica conectividade real com PostgreSQL, Redis (via PING + SCAN não-bloqueante),
    chaves de API, estado do Kill-Switch global e modo Sandbox.
    """
    cfg_memoria = SettingsService.obter_cache_memoria()
    saude = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ambiente": settings.ENVIRONMENT,
        "gateway_whatsapp": "send_inteligentte" if settings.SEND_API_KEY else "uazapi",
        "ia_silenciada_global": cfg_memoria.ia_silenciada_global,
        "modo_24h_inbound": cfg_memoria.modo_24h_inbound,
        "sandbox_mode": settings.SANDBOX_MODE,
        "buffers_pendentes": 0,
        "tasks_ativas": get_active_background_tasks_count(),
        "componentes": {},
    }

    # 1. Checa PostgreSQL
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT 1"))
            saude["componentes"]["postgres"] = "conectado" if res.scalar() == 1 else "erro"
    except Exception as e:
        saude["componentes"]["postgres"] = f"erro: {str(e)}"
        saude["status"] = "degraded"

    # 2. Checa Redis + contagem não-bloqueante de buffers
    try:
        pong = await redis_client.ping()
        saude["componentes"]["redis"] = "conectado" if pong else "erro"
        if pong:
            saude["buffers_pendentes"] = await default_redis_buffer_gateway.contar_buffers_pendentes()
    except Exception as e:
        saude["componentes"]["redis"] = f"erro: {str(e)}"
        saude["status"] = "degraded"

    # 3. Checa Chaves de Serviços Externos e Alertas Operacionais
    saude["componentes"]["uazapi_token"] = bool(settings.UAZAPI_TOKEN)
    saude["componentes"]["send_api_key"] = bool(settings.SEND_API_KEY)
    saude["componentes"]["openai_key"] = bool(settings.OPENAI_API_KEY)

    try:
        alerta_cota = await redis_client.get("alerta_sistema:openai_sem_creditos")
        if alerta_cota:
            saude["componentes"]["openai_creditos"] = "esgotado"
            saude["alerta_operacional"] = (
                "Créditos da OpenAI esgotados! Leads recebidos foram direcionados ao transbordo humano sem disparos automáticos."
            )
            saude["status"] = "degraded"
        else:
            saude["componentes"]["openai_creditos"] = "operante"
    except Exception:
        saude["componentes"]["openai_creditos"] = "desconhecido"

    tem_gateway_whatsapp = bool(saude["componentes"]["uazapi_token"] or saude["componentes"]["send_api_key"])
    if not tem_gateway_whatsapp or not saude["componentes"]["openai_key"]:
        saude["status"] = "degraded"

    if saude["status"] != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return saude


app.include_router(leads.router)
app.include_router(webhook.router)
app.include_router(webhook.router, prefix="/webhooks", include_in_schema=False)
app.include_router(analytics.router)
app.include_router(settings_router.router)
app.include_router(auth_router.router)
