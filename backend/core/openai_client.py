"""
Pool único e centralizado do cliente assíncrono da OpenAI (Singleton Pattern).
Reutiliza conexões HTTP/2 internas do httpx, eliminando handshakes TLS desnecessários,
e centraliza utilitários de diagnóstico de falhas de cota/faturamento (DRY).
"""

from openai import AsyncOpenAI, RateLimitError
from core.config import settings

openai_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY if settings.OPENAI_API_KEY else None,
    timeout=settings.OPENAI_TIMEOUT_SECONDS,
    max_retries=settings.OPENAI_MAX_RETRIES,
)

_QUOTA_ERROR_MARKERS = (
    "insufficient_quota",
    "quota_exceeded",
    "exceeded your current quota",
    "credit_balance_exhausted",
    "no credits remaining",
    "billing_hard_limit_reached",
)


def is_openai_quota_error(exc: BaseException) -> bool:
    """
    Identifica se uma exceção da OpenAI decorre de esgotamento real de créditos/cota
    (HTTP 429 insufficient_quota / billing_hard_limit_reached) em vez de rate-limit transitório.
    """
    if isinstance(exc, RateLimitError):
        code = str(getattr(exc, "code", "") or "").lower()
        body = str(getattr(exc, "body", "") or "").lower()
        msg = str(exc).lower()
        combined = f"{code} {body} {msg}"
        return any(marker in combined for marker in _QUOTA_ERROR_MARKERS)

    texto = str(exc).lower()
    return any(marker in texto for marker in _QUOTA_ERROR_MARKERS)
