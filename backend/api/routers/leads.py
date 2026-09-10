from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from typing import List

from core.database import get_db
from core.logger import logger
from services import buffer_service
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
    logger.info(f"[LEADS] Lead criado manualmente: {novo_lead.nome} ({novo_lead.telefone})")
    return novo_lead

@router.get("/", response_model=List[schemas.LeadResponse])
async def listar_leads(db: AsyncSession = Depends(get_db)):
    """Lista todos os clientes (Leads) cadastrados"""
    resultado = await db.execute(select(models.Lead))
    leads = resultado.scalars().all()
    return leads

@router.delete("/{lead_id}", status_code=204)
async def deletar_lead(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Deleta um Lead e todo o seu histórico de mensagens do banco de dados (exclusão em cascata).
    """
    query = select(models.Lead).where(models.Lead.id == lead_id)
    resultado = await db.execute(query)
    lead = resultado.scalars().first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
        
    # 1. Apaga primeiro todas as interações vinculadas a esse lead
    await db.execute(delete(models.Interacao).where(models.Interacao.lead_id == lead_id))
    
    # 2. Apaga o lead
    await db.delete(lead)
    await db.commit()
    
    # 3. Limpa qualquer buffer residual no Redis
    await buffer_service.obter_e_limpar_buffer(lead.telefone)
    
    logger.info(f"[LEADS] 🗑️ Lead e histórico apagados com sucesso (ID: {lead_id})")
    return

@router.delete("/{lead_id}/interacoes", status_code=200)
async def limpar_historico_conversa(lead_id: int, db: AsyncSession = Depends(get_db)):
    """
    Apaga apenas as mensagens trocadas com o Lead, mantendo o cadastro do cliente.
    Útil para fazer a IA 'esquecer' a conversa e reiniciar um diálogo do zero.
    """
    query = select(models.Lead).where(models.Lead.id == lead_id)
    resultado = await db.execute(query)
    lead = resultado.scalars().first()
    
    if not lead:
        raise HTTPException(status_code=404, detail="Lead não encontrado")
        
    await db.execute(delete(models.Interacao).where(models.Interacao.lead_id == lead_id))
    lead.status = models.LeadStatus.NOVO
    await db.commit()
    
    # Limpa buffer do Redis
    await buffer_service.obter_e_limpar_buffer(lead.telefone)
    
    logger.info(f"[LEADS] 🧹 Histórico de conversa limpo para o Lead ID {lead_id} ({lead.telefone})")
    return {"status": "historico_limpo", "lead_id": lead_id, "novo_status": "NOVO_LEAD"}

@router.delete("/reset/por-telefone/{telefone}", status_code=200)
async def resetar_lead_por_telefone(telefone: str, db: AsyncSession = Depends(get_db)):
    """
    Busca o lead pelo número de telefone (ou parte dele, ex: 91923098)
    e deleta tanto o cadastro quanto todo o histórico de mensagens e buffers.
    """
    digitos = "".join(filter(str.isdigit, telefone))
    query = select(models.Lead).where(models.Lead.telefone.contains(digitos))
    resultado = await db.execute(query)
    lead = resultado.scalars().first()
    
    if not lead:
        # Se nem o lead existe, garante a limpeza do Redis por precaução
        await buffer_service.obter_e_limpar_buffer(telefone)
        return {"status": "lead_nao_existia", "telefone": telefone}
        
    lead_id = lead.id
    tel_completo = lead.telefone
    
    # Apaga interações e lead
    await db.execute(delete(models.Interacao).where(models.Interacao.lead_id == lead_id))
    await db.delete(lead)
    await db.commit()
    
    # Limpa buffer do Redis
    await buffer_service.obter_e_limpar_buffer(tel_completo)
    
    logger.info(f"[LEADS] 💥 Reset completo realizado para o número {tel_completo} (Lead ID: {lead_id})")
    return {"status": "reset_sucesso", "lead_id": lead_id, "telefone": tel_completo}

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
