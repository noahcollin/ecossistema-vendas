from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from core.config import settings

# Cria o 'Motor' de conexão com o PostgreSQL de forma assíncrona com pool dimensionado para alta concorrência
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=True
)

# Cria a fábrica de 'Sessões' (cada sessão é uma conversa separada com o banco)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Cria a classe Base no padrão moderno do SQLAlchemy 2.0
class Base(DeclarativeBase):
    pass

# Função para pegarmos uma sessão do banco sempre que precisarmos (Injeção de Dependência)
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
