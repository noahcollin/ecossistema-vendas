"""
Configurações e fixtures globais de teste para pytest e pytest-asyncio.
Fornece sessões de banco de dados isoladas e mocks para os gateways do sistema.
"""

from typing import AsyncGenerator, Any
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import AsyncSessionLocal, engine, Base


class MockWhatsAppGateway:
    """Implementação em memória de WhatsAppGatewayProtocol para testes unitários."""

    def __init__(self) -> None:
        self.mensagens_enviadas: list[dict[str, Any]] = []
        self.presencas_enviadas: list[dict[str, Any]] = []

    async def enviar_presenca(
        self,
        telefone: str,
        presenca: str = "composing",
        delay_ms: int = 15000
    ) -> dict[str, Any]:
        self.presencas_enviadas.append({"telefone": telefone, "presenca": presenca, "delay_ms": delay_ms})
        return {"status": "sucesso"}

    async def enviar_mensagem(
        self,
        telefone: str,
        texto: str,
        delay_ms: int = 2000,
        max_retries: int = 2
    ) -> dict[str, Any]:
        self.mensagens_enviadas.append({"telefone": telefone, "texto": texto, "delay_ms": delay_ms})
        return {"status": "sucesso", "dados": {"id": f"mock_msg_{len(self.mensagens_enviadas)}"}}

    async def enviar_mensagem_humanizada(
        self,
        telefone: str,
        texto_bruto: str,
        delay_base_ms: int = 1500,
        simular_digitacao: bool = True,
        intervalo_entre_baloes: float = 1.8
    ) -> tuple[list[str], bool]:
        partes = [p.strip() for p in texto_bruto.split("|||") if p.strip()] or [texto_bruto]
        for p in partes:
            self.mensagens_enviadas.append({"telefone": telefone, "texto": p})
        return partes, True

    async def baixar_arquivo(
        self,
        message_id: str,
        generate_mp3: bool = False
    ) -> dict[str, Any]:
        return {"fileURL": f"https://mock.cdn/{message_id}", "mimetype": "application/pdf"}


class MockCacheBufferGateway:
    """Implementação em memória de CacheBufferProtocol para testes unitários."""

    def __init__(self) -> None:
        self.buffers: dict[str, list[str]] = {}
        self.timestamps: dict[str, str] = {}
        self.counter = 0

    async def adicionar_mensagem(self, telefone: str, texto: str) -> str:
        self.counter += 1
        token = str(self.counter)
        self.buffers.setdefault(telefone, []).append(texto)
        self.timestamps[telefone] = token
        return token

    async def obter_e_limpar_buffer(self, telefone: str) -> list[str]:
        mensagens = self.buffers.pop(telefone, [])
        self.timestamps.pop(telefone, None)
        return mensagens

    async def verificar_se_e_ultima(self, telefone: str, token_disparado: str | float) -> bool:
        return str(self.timestamps.get(telefone, "")) == str(token_disparado)


@pytest_asyncio.fixture(scope="session")
async def setup_test_db():
    """Garante que as tabelas existem no início da suíte."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def db_session(setup_test_db) -> AsyncGenerator[AsyncSession, None]:
    """Fixture que fornece uma sessão assíncrona do banco para cada teste."""
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
def mock_whatsapp() -> MockWhatsAppGateway:
    """Fixture com gateway mockado do WhatsApp."""
    return MockWhatsAppGateway()


@pytest.fixture
def mock_buffer() -> MockCacheBufferGateway:
    """Fixture com buffer mockado em memória."""
    return MockCacheBufferGateway()
