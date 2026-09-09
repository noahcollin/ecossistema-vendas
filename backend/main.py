from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text

# Importamos as configurações que acabamos de criar
from database import get_db, Base, engine
import models  # Importamos models para o SQLAlchemy criar a tabela
import schemas # Importamos nossas regras de validação (Pydantic)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Roda uma única vez ANTES do servidor ligar e aceitar requisições
    async with engine.begin() as conn:
        # ATENÇÃO: Isso cria as tabelas automaticamente se não existirem.
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title="Ecossistema de Vendas Autônomo API",
    description="Core Backend para gerenciamento da máquina de estados de leads",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/")
async def root():
    return {"message": "API do Ecossistema de Vendas operante!"}

# Rota para testar a comunicação com o Banco de Dados
@app.get("/db-check")
async def check_db(db: AsyncSession = Depends(get_db)):
    try:
        # Manda uma query básica "SELECT 1" para ver se o banco responde
        result = await db.execute(text("SELECT 1"))
        if result.scalar() == 1:
            return {"status": "sucesso", "mensagem": "Conexão com o PostgreSQL está perfeita!"}
    except Exception as e:
        return {"status": "erro", "mensagem": f"Falha ao conectar: {str(e)}"}

# ----------------- NOVAS ROTAS (LEADS) -----------------

@app.post("/leads", response_model=schemas.LeadResponse, status_code=201)
async def criar_lead(lead: schemas.LeadCreate, db: AsyncSession = Depends(get_db)):
    """Cria um novo cliente (Lead) no banco de dados"""
    
    # Primeiro checamos se já existe um lead com esse telefone
    query = select(models.Lead).where(models.Lead.telefone == lead.telefone)
    resultado = await db.execute(query)
    lead_existente = resultado.scalars().first()
    
    if lead_existente:
        raise HTTPException(status_code=400, detail="Telefone já cadastrado no sistema")
        
    # Se não existir, criamos um novo lead em branco, mas com os dados informados
    novo_lead = models.Lead(
        nome=lead.nome,
        telefone=lead.telefone
    )
    
    # Salva no banco de dados
    db.add(novo_lead)
    await db.commit()
    await db.refresh(novo_lead) # Pega o ID automático que o banco gerou
    
    return novo_lead

@app.get("/leads", response_model=list[schemas.LeadResponse])
async def listar_leads(db: AsyncSession = Depends(get_db)):
    """Busca e retorna todos os clientes cadastrados"""
    
    query = select(models.Lead)
    resultado = await db.execute(query)
    leads = resultado.scalars().all()
    
    return leads


