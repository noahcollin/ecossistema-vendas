"""
Roteador FastAPI para Gestão e Customização das Configurações Operacionais ("Sala de Máquinas").
Fornece endpoints para o Dashboard ler e atualizar preços, produtos, pacing, cadência, horários,
além de ações críticas de governança (Kill-Switch Global e Expurgo de Filas Voláteis Redis).
Protegido por autenticação de administrador com resistência a timing attacks.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import validar_admin_api_key
from services.settings import SettingsService
from schemas.settings import (
    OperacaoSettingsResponse,
    OperacaoSettingsUpdate,
    KillSwitchRequest,
    KillSwitchResponse,
    RedisPurgeResponse,
)

router = APIRouter(
    prefix="/settings",
    tags=["Configurações Operacionais"],
    dependencies=[Depends(validar_admin_api_key)]
)


@router.get(
    "/operacao",
    response_model=OperacaoSettingsResponse,
    summary="Obter configurações operacionais ativas",
    description="Retorna as regras comerciais vigentes: catálogo de produtos, preços, pacing, cadência de follow-up, horário comercial e estado do Kill-Switch."
)
async def obter_configuracoes(db: AsyncSession = Depends(get_db)) -> OperacaoSettingsResponse:
    """Retorna os parâmetros de operação vigentes com cache no Redis."""
    return await SettingsService.obter_configuracoes(db)


@router.put(
    "/operacao",
    response_model=OperacaoSettingsResponse,
    summary="Atualizar configurações operacionais",
    description="Permite que o gestor atualize preços de produtos, itens do catálogo, pacing, regras de cadência e horários em tempo real."
)
async def atualizar_configuracoes(
    payload: OperacaoSettingsUpdate,
    db: AsyncSession = Depends(get_db)
) -> OperacaoSettingsResponse:
    """Atualiza as configurações, sincroniza o banco, limpa cache e ajusta runtime."""
    return await SettingsService.atualizar_configuracoes(db, payload)


@router.post(
    "/kill-switch",
    response_model=KillSwitchResponse,
    summary="Alternar Kill-Switch global da operação autônoma de IA",
    description="Pausa ou retoma instantaneamente todas as respostas autônomas da IA e disparos de follow-up, mantendo a captura passiva de mensagens."
)
async def alternar_kill_switch(
    payload: KillSwitchRequest,
    db: AsyncSession = Depends(get_db)
) -> KillSwitchResponse:
    """Ativa ou desativa o silenciamento global da IA."""
    return await SettingsService.alternar_kill_switch(db, silenciar=payload.silenciar)


@router.post(
    "/redis/purge",
    response_model=RedisPurgeResponse,
    summary="Expurgar filas voláteis de debounce e locks no Redis",
    description="Limpa de forma segura e não-bloqueante (via SCAN) buffers de mensagens em espera e locks órfãos no Redis."
)
async def expurgar_filas_redis() -> RedisPurgeResponse:
    """Expurga chaves voláteis de debounce/locks do Redis sem afetar dados persistidos."""
    return await SettingsService.expurgar_filas_redis()
