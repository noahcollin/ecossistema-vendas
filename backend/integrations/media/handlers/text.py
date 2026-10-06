"""
Handler de Mídia para Mensagens de Texto padrão ou legendas soltas.
"""

from typing import Any
import schemas
from .base import BaseMediaHandler


class TextMediaHandler(BaseMediaHandler):
    """Estratégia fallback para Mensagens de Texto padrão ou legendas soltas."""

    def can_handle(
        self,
        message: schemas.UazapiMessage,
        content_dict: dict[str, Any],
        tipo: str,
        file_url: str
    ) -> bool:
        # Handler padrão final: aceita qualquer mensagem com texto
        texto = (message.text or "").strip()
        legenda = texto or content_dict.get("caption") or ""
        return bool(legenda)

    async def handle(
        self,
        message: schemas.UazapiMessage,
        content_dict: dict[str, Any],
        legenda: str
    ) -> str:
        return legenda
