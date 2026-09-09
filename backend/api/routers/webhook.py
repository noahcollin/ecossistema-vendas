from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_db
import models
import schemas
from services import ai_service, uazapi_service

router = APIRouter(prefix="/webhook", tags=["Webhook (Uazapi)"])

@router.post("/uazapi")
async def webhook_uazapi(payload: schemas.UazapiPayload, db: AsyncSession = Depends(get_db)):
    """Webhook Inteligente: Cria lead, responde com IA e salva interações automaticamente"""
    try:
        if not payload.chat or not payload.chat.phone:
            return {"status": "ignorado", "motivo": "sem telefone"}
            
        telefone = payload.chat.phone
        nome_contato = payload.chat.name or (payload.message.senderName if payload.message else "Desconhecido")
        
        # 1. Verifica Lead
        query = select(models.Lead).where(models.Lead.telefone == telefone)
        resultado = await db.execute(query)
        lead_existente = resultado.scalars().first()
        
        if not lead_existente:
            novo_lead = models.Lead(nome=nome_contato, telefone=telefone)
            db.add(novo_lead)
            await db.commit()
            await db.refresh(novo_lead)
            lead_existente = novo_lead
            print(f"\n[UAZAPI] 🔥 NOVO LEAD CADASTRADO: {nome_contato}")

        # 2. Salva a mensagem do Cliente
        texto_mensagem = payload.message.text if payload.message and payload.message.text else "[Áudio ou Mídia não suportada]"
        
        nova_interacao = models.Interacao(
            lead_id=lead_existente.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto=texto_mensagem
        )
        db.add(nova_interacao)
        await db.commit()
        print(f"[CLIENTE] 🗨️ {texto_mensagem}")
        
        # 3. Puxa o histórico de conversas do banco para a IA ler
        query_historico = select(models.Interacao).where(models.Interacao.lead_id == lead_existente.id).order_by(models.Interacao.criado_em)
        resultado_historico = await db.execute(query_historico)
        historico_completo = resultado_historico.scalars().all()
        
        # 4. Pensa (IA gera a resposta)
        print(f"[IA] 🧠 Pensando...")
        resposta_ia = await ai_service.gerar_resposta_vendedor(nome_contato, historico_completo)
        print(f"[IA] 🤖 {resposta_ia}")
        
        # 5. Salva a resposta da IA no histórico
        interacao_sistema = models.Interacao(
            lead_id=lead_existente.id,
            origem=models.InteracaoOrigem.SISTEMA,
            texto=resposta_ia
        )
        db.add(interacao_sistema)
        await db.commit()
        
        # 6. Manda a resposta pro cliente no WhatsApp! (A Boca)
        await uazapi_service.enviar_mensagem(telefone, resposta_ia)
            
        return {"status": "processado_com_ia"}
    except Exception as e:
        print(f"❌ [WEBHOOK ERRO]: {e}")
        return {"status": "erro", "detalhe": str(e)}
