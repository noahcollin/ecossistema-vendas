"""
Implementações concretas de Handlers de Mídia seguindo o Strategy Pattern (OCP).
"""

from typing import Any
import schemas

from integrations.media.handlers.base import BaseMediaHandler
from integrations.media.handlers.vision_handler import processar_imagem
from integrations.media.handlers.gif_handler import processar_gif_ou_video
from integrations.media.handlers.audio_handler import processar_audio
from integrations.media.handlers.pdf_handler import processar_documento


class GifOrVideoHandler(BaseMediaHandler):
    """Estratégia para GIF, Animações e Vídeos."""

    def can_handle(
        self,
        message: schemas.UazapiMessage,
        content_dict: dict[str, Any],
        tipo: str,
        file_url: str
    ) -> bool:
        eh_gif = (
            "gif" in tipo
            or ".gif" in file_url
            or bool(content_dict.get("gifPlayback"))
            or bool(content_dict.get("isGif"))
            or "gif" in str(content_dict.get("mimetype", "")).lower()
        )
        eh_video = (
            "video" in tipo
            or any(ext in file_url for ext in [".mp4", ".mov", ".avi", ".mkv"])
            or "video" in str(content_dict.get("mimetype", "")).lower()
        )
        return eh_gif or eh_video

    async def handle(
        self,
        message: schemas.UazapiMessage,
        content_dict: dict[str, Any],
        legenda: str
    ) -> str:
        tipo = (message.messageType or "").lower()
        file_url = (message.fileURL or "").lower()
        eh_gif = (
            "gif" in tipo
            or ".gif" in file_url
            or bool(content_dict.get("gifPlayback"))
            or bool(content_dict.get("isGif"))
            or "gif" in str(content_dict.get("mimetype", "")).lower()
        )
        return await processar_gif_ou_video(message, content_dict, legenda, eh_gif=eh_gif)


class ImageMediaHandler(BaseMediaHandler):
    """Estratégia para Imagens estáticas e Figurinhas (Stickers)."""

    def can_handle(
        self,
        message: schemas.UazapiMessage,
        content_dict: dict[str, Any],
        tipo: str,
        file_url: str
    ) -> bool:
        return (
            "image" in tipo
            or "sticker" in tipo
            or any(ext in file_url for ext in [".jpg", ".jpeg", ".png", ".webp"])
        )

    async def handle(
        self,
        message: schemas.UazapiMessage,
        content_dict: dict[str, Any],
        legenda: str
    ) -> str:
        return await processar_imagem(message, content_dict, legenda)


class AudioMediaHandler(BaseMediaHandler):
    """Estratégia para Mensagens de Áudio e Voz (PTT)."""

    def can_handle(
        self,
        message: schemas.UazapiMessage,
        content_dict: dict[str, Any],
        tipo: str,
        file_url: str
    ) -> bool:
        return (
            "audio" in tipo
            or "voice" in tipo
            or "ptt" in tipo
            or any(ext in file_url for ext in [".mp3", ".ogg", ".opus", ".m4a", ".wav"])
        )

    async def handle(
        self,
        message: schemas.UazapiMessage,
        content_dict: dict[str, Any],
        legenda: str
    ) -> str:
        return await processar_audio(message, content_dict)


class DocumentMediaHandler(BaseMediaHandler):
    """Estratégia para Documentos e Arquivos PDF."""

    def can_handle(
        self,
        message: schemas.UazapiMessage,
        content_dict: dict[str, Any],
        tipo: str,
        file_url: str
    ) -> bool:
        return "document" in tipo or ".pdf" in file_url

    async def handle(
        self,
        message: schemas.UazapiMessage,
        content_dict: dict[str, Any],
        legenda: str
    ) -> str:
        return await processar_documento(message, content_dict, legenda)


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
