"""
Contratos de abstração (Protocols) para Inversão de Dependências (DIP).
Permitem desacoplar serviços de domínio das implementações concretas de infraestrutura
(Uazapi, Redis, OpenAI), viabilizando injeção de dependências e testes unitários isolados com mocks.
"""

from typing import Protocol, Any, runtime_checkable


@runtime_checkable
class WhatsAppGatewayProtocol(Protocol):
    """Contrato abstrato para gateway de comunicação via WhatsApp."""

    async def enviar_presenca(
        self,
        telefone: str,
        presenca: str = "composing",
        delay_ms: int = 15000
    ) -> dict[str, Any]:
        ...

    async def enviar_mensagem(
        self,
        telefone: str,
        texto: str,
        delay_ms: int = 2000,
        max_retries: int = 2
    ) -> dict[str, Any]:
        ...

    async def enviar_mensagem_humanizada(
        self,
        telefone: str,
        texto_bruto: str,
        delay_base_ms: int = 1500,
        simular_digitacao: bool = True,
        intervalo_entre_baloes: float = 1.8
    ) -> tuple[list[str], bool]:
        ...

    async def baixar_arquivo(
        self,
        message_id: str,
        generate_mp3: bool = False
    ) -> dict[str, Any]:
        ...


@runtime_checkable
class CacheBufferProtocol(Protocol):
    """Contrato abstrato para operações de buffer e debounce em memória volátil/cache."""

    async def adicionar_mensagem(
        self,
        telefone: str,
        texto: str
    ) -> str:
        ...

    async def obter_e_limpar_buffer(
        self,
        telefone: str
    ) -> list[str]:
        ...

    async def verificar_se_e_ultima(
        self,
        telefone: str,
        token_disparado: str | float
    ) -> bool:
        ...
