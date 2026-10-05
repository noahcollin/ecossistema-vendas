"""
Pool único e centralizado do cliente assíncrono da OpenAI (Singleton Pattern).
Reutiliza conexões HTTP/2 internas do httpx, eliminando handshakes TLS desnecessários.
"""

from openai import AsyncOpenAI
from core.config import settings

openai_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY if settings.OPENAI_API_KEY else None,
    timeout=settings.OPENAI_TIMEOUT_SECONDS,
    max_retries=settings.OPENAI_MAX_RETRIES,
)
