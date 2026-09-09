from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List

from core.database import get_db
import models
import schemas

router = APIRouter(prefix="/leads", tags=["Leads"])

@router.post("/", response_model=schemas.LeadResponse)
async def criar_lead(lead: schemas.LeadCreate, db: AsyncSession = Depends(get_db)):
    """Cria um novo cliente (Lead) manualmente"""
    novo_lead = models.Lead(
        nome=lead.nome,
        telefone=lead.telefone,
        status=lead.status
    )
    db.add(novo_lead)
    await db.commit()
    await db.refresh(novo_lead)
    return novo_lead

@router.get("/", response_model=List[schemas.LeadResponse])
async def listar_leads(db: AsyncSession = Depends(get_db)):
    """Lista todos os clientes (Leads) cadastrados"""
    resultado = await db.execute(select(models.Lead))
    leads = resultado.scalars().all()
    return leads

@router.delete("/{lead_id}", status_code=204)
async def deletar_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """Deleta um cliente (Lead) do banco de dados pelo ID (útil para testes)"""
    query = select(models.Lead).where(models.Lead.id == lead_id)
    resultado = await db.execute(query)
    lead = resultado.scalars().first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
        
    await db.delete(lead)
    await db.commit()
    print(f"🗑️ Lead apagado com sucesso (ID: {lead_id})")
    return

@router.get("/{lead_id}/interacoes")
async def listar_interacoes(lead_id: int, db: AsyncSession = Depends(get_db)):
    """Lista o histórico de conversas (Interações) de um cliente"""
    query = select(models.Interacao).where(models.Interacao.lead_id == lead_id).order_by(models.Interacao.criado_em)
    resultado = await db.execute(query)
    interacoes = resultado.scalars().all()
    
    return [{
        "id": i.id, 
        "origem": i.origem.value, 
        "texto": i.texto, 
        "data": i.criado_em.isoformat()
    } for i in interacoes]
