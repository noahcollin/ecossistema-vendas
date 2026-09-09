from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_db
import models
import schemas

router = APIRouter(prefix="/webhook", tags=["Webhook (Uazapi)"])

@router.post("/uazapi")
async def webhook_uazapi(payload: schemas.UazapiPayload, db: AsyncSession = Depends(get_db)):
    """Webhook Inteligente: Cria um lead e salva interações automaticamente"""
    try:
        # Verifica se recebemos as informações necessárias (telefone)
        if not payload.chat or not payload.chat.phone:
            print("Webhook recebido sem telefone, ignorando.")
            return {"status": "ignorado", "motivo": "sem telefone"}
            
        telefone = payload.chat.phone
        nome_contato = payload.chat.name or (payload.message.senderName if payload.message else "Desconhecido")
        
        # 1. Verifica se o Lead já existe no banco
        query = select(models.Lead).where(models.Lead.telefone == telefone)
        resultado = await db.execute(query)
        lead_existente = resultado.scalars().first()
        
        if lead_existente:
            print(f"\n[UAZAPI] 🗨️ Mensagem recebida de Lead já existente: {nome_contato} ({telefone})")
        else:
            # 2. Se não existe, cria a ficha dele automaticamente!
            novo_lead = models.Lead(nome=nome_contato, telefone=telefone)
            db.add(novo_lead)
            await db.commit()
            await db.refresh(novo_lead)
            lead_existente = novo_lead
            print(f"\n[UAZAPI] 🔥 NOVO LEAD CADASTRADO AUTOMATICAMENTE: {nome_contato} ({telefone})")

        # 3. Agora que temos o cliente garantido, vamos salvar o "post-it" (a mensagem dele)
        texto_mensagem = payload.message.text if payload.message and payload.message.text else "[Mensagem sem texto ou Mídia]"
        
        nova_interacao = models.Interacao(
            lead_id=lead_existente.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=texto_mensagem
        )
        db.add(nova_interacao)
        await db.commit()
        print(f"[UAZAPI] 📝 Mensagem salva no histórico do {nome_contato}: '{texto_mensagem}'\n")
            
        return {"status": "processado"}
    except Exception as e:
        print(f"Erro ao processar webhook da Uazapi: {e}")
        return {"status": "erro", "detalhe": str(e)}
