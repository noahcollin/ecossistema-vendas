"""
Roteador de Analytics, Métricas e Business Intelligence Comercial (FastAPI).
Entrega endpoints otimizados para alimentar a visão executiva e operacional do Dashboard.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import validar_admin_api_key
from services.lead import AnalyticsService
import schemas

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics & BI"],
    dependencies=[Depends(validar_admin_api_key)]
)


@router.get("/overview", response_model=schemas.DashboardOverviewResponse)
async def obter_visao_geral(db: AsyncSession = Depends(get_db)):
    """
    Retorna o panorama executivo consolidado com os 5 blocos de inteligência comercial:
    - Métricas Financeiras & Pipeline
    - Saúde do Funil & Priorização de Leads
    - Aquisição & ROI por Canal de Tráfego
    - Inteligência de Perdas & Objeções
    - Operação de Conversas & Eficácia do Follow-up
    """
    return await AnalyticsService.obter_visao_geral(db)


@router.get("/financeiro", response_model=schemas.FinanceiroKPIs)
async def obter_kpis_financeiros(db: AsyncSession = Depends(get_db)):
    """Retorna os indicadores financeiros de pipeline ativo, receita ganha e conversão."""
    return await AnalyticsService.obter_metricas_financeiras(db)


@router.get("/funil", response_model=schemas.FunilKPIs)
async def obter_kpis_funil(db: AsyncSession = Depends(get_db)):
    """Retorna a distribuição volumétrica e em R$ por etapa do funil e temperatura dos leads."""
    return await AnalyticsService.obter_metricas_funil(db)


@router.get("/aquisicao", response_model=schemas.AquisicaoKPIs)
async def obter_kpis_aquisicao(db: AsyncSession = Depends(get_db)):
    """Retorna a eficácia e receita discriminada por canal de captação e tipo de entrada (Inbound vs Outbound)."""
    return await AnalyticsService.obter_metricas_aquisicao(db)


@router.get("/perdas", response_model=schemas.PerdasKPIs)
async def obter_kpis_perdas(
    limite: int = Query(10, ge=1, le=50, description="Quantidade de motivos no ranking"),
    db: AsyncSession = Depends(get_db)
):
    """Retorna o ranking de motivos de perda e objeções comerciais mapeadas pela IA."""
    return await AnalyticsService.obter_metricas_perdas(db, limite=limite)


@router.get("/conversas", response_model=schemas.ConversasKPIs)
async def obter_kpis_conversas(db: AsyncSession = Depends(get_db)):
    """Retorna o volume de mensagens no WhatsApp e a taxa de resgate da cadência de follow-up."""
    return await AnalyticsService.obter_metricas_conversas(db)
