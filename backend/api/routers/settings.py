"""
Roteador FastAPI para Gestão e Customização das Configurações Operacionais.
Fornece endpoints para o Dashboard ler e atualizar preços, produtos, cadência e horários.
Protegido por autenticação de administrador com resistência a timing attacks.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.security import validar_admin_api_key
from services.settings import SettingsService
from schemas.settings import OperacaoSettingsResponse, OperacaoSettingsUpdate

router = APIRouter(
    prefix="/settings",
    tags=["Configurações Operacionais"],
    dependencies=[Depends(validar_admin_api_key)]
)


@router.get(
    "/operacao",
    response_model=OperacaoSettingsResponse,
    summary="Obter configurações operacionais ativas",
    description="Retorna as regras comerciais vigentes: catálogo de produtos, preços, cadência de follow-up e horário comercial."
)
async def obter_configuracoes(db: AsyncSession = Depends(get_db)):
    """Retorna os parâmetros de operação vigentes com cache no Redis."""
    return await SettingsService.obter_configuracoes(db)


@router.put(
    "/operacao",
    response_model=OperacaoSettingsResponse,
    summary="Atualizar configurações operacionais",
    description="Permite que o gestor atualize preços de produtos, novos itens do catálogo, regras de cadência e horários em tempo real."
)
async def atualizar_configuracoes(
    payload: OperacaoSettingsUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Atualiza as configurações, sincroniza o banco, limpa cache e ajusta runtime."""
    return await SettingsService.atualizar_configuracoes(db, payload)
