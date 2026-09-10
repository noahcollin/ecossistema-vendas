import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env (se existir)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Pega a URL do banco de dados do ambiente (ou usa uma padrão de erro se não achar)
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL não configurada no arquivo .env")

# Permite ligar logs detalhados de SQL apenas se explicitamente configurado no .env
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"

# Cria o 'Motor' de conexão com o PostgreSQL de forma assíncrona (super rápida)
engine = create_async_engine(DATABASE_URL, echo=SQL_ECHO)

# Cria a fábrica de 'Sessões' (cada sessão é uma conversa separada com o banco)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Cria a classe Base, que será a "mãe" de todas as nossas tabelas
Base = declarative_base()

# Função para pegarmos uma sessão do banco sempre que precisarmos (Injeção de Dependência)
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
