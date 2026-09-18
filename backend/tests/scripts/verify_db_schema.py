import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import text
from core.database import AsyncSessionLocal
import models
import schemas

async def check():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'leads' ORDER BY ordinal_position;"))
        rows = res.fetchall()
        print("--- COLUNAS NA TABELA LEADS ---")
        for col, typ in rows:
            print(f"  • {col}: {typ}")
            
    print("\n--- TESTE SCHEMA RESPONSE ---")
    lead_sample = schemas.LeadResponse(
        id=1,
        telefone="558399999999",
        etapa_funil=models.EtapaFunil.QUALIFICACAO,
        desfecho=models.DesfechoLead.EM_ANDAMENTO,
        controle=models.ControleAtendimento.PILOTO_IA,
        temperatura=models.TemperaturaLead.QUENTE,
        valor_estimado=2500.0,
        tags=["comercio", "urgente"],
        motivo_perda=None
    )
    print("LeadResponse serialization:", lead_sample.model_dump())
    print("Schema OK!")

if __name__ == "__main__":
    asyncio.run(check())
