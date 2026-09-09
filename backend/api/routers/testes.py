from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from core.database import get_db
import schemas
from services import uazapi_service

router = APIRouter(tags=["Testes Essenciais"])

@router.get("/db-check")
async def check_db(db: AsyncSession = Depends(get_db)):
    """Rota para testar a comunicação com o Banco de Dados"""
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            return {"status": "sucesso", "mensagem": "Conexão com o PostgreSQL está perfeita!"}
    except Exception as e:
        return {"status": "erro", "detalhe": str(e)}

@router.post("/teste-envio")
async def teste_enviar_mensagem(dados: schemas.TesteEnvio):
    """Rota temporária de teste para disparar uma mensagem ativamente (A Boca)"""
    resultado = await uazapi_service.enviar_mensagem(dados.telefone, dados.texto)
    return resultado
