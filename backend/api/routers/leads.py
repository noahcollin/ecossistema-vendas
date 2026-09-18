from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any

from core.database import get_db
from services.lead_service import LeadService
import schemas

router = APIRouter(prefix="/leads", tags=["Leads"])

@router.post("/", response_model=schemas.LeadResponse)
async def criar_lead(lead: schemas.LeadCreate, db: AsyncSession = Depends(get_db)):
    """Cria um novo cliente (Lead) manualmente."""
    return await LeadService.criar_lead(db, lead)

@router.get("/", response_model=List[schemas.LeadResponse])
async def listar_leads(db: AsyncSession = Depends(get_db)):
    """Lista todos os clientes (Leads) cadastrados."""
    return await LeadService.listar_leads(db)

@router.delete("/{lead_id}", status_code=204)
async def deletar_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Deleta um Lead e todo o seu histórico de mensagens do banco de dados (exclusão em cascata).
    """
    await LeadService.deletar_lead(db, lead_id)
    return

@router.delete("/{lead_id}/interacoes", status_code=200)
async def limpar_historico_conversa(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Apaga apenas as mensagens trocadas com o Lead, mantendo o cadastro do cliente.
    Útil para fazer a IA 'esquecer' a conversa e reiniciar um diálogo do zero.
    """
    return await LeadService.limpar_historico_conversa(db, lead_id)

@router.delete("/reset/por-telefone/{telefone}", status_code=200)
async def resetar_lead_por_telefone(telefone: str, db: AsyncSession = Depends(get_db)):
    """
    Busca o lead pelo número de telefone (mínimo de 8 dígitos)
    e deleta tanto o cadastro quanto todo o histórico de mensagens e buffers.
    """
    return await LeadService.resetar_lead_por_telefone(db, telefone)

@router.get("/{lead_id}/interacoes")
async def listar_interacoes(lead_id: int, db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """Lista o histórico de conversas (Interações) de um cliente."""
    return await LeadService.listar_interacoes(db, lead_id)

@router.post("/{lead_id}/auditar", response_model=schemas.LeadResponse)
async def auditar_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Aciona o Agente Auditor de Negócios (DealAuditorAgent) para gerar
    o Dossiê Comercial Executivo completo do lead sob demanda.
    """
    return await LeadService.gerar_dossie_lead(db, lead_id)


