"""
Pacote Modular de Processamento e Inteligência de Mídias.
Arquitetura baseada em Strategy Pattern e Open-Closed Principle (OCP).
Novos tipos de mídia podem ser plugados registrando instâncias de BaseMediaHandler.
"""

import json
from typing import Any
import schemas
from core.logger import logger

from integrations.media.handlers import (
    BaseMediaHandler,
    GifOrVideoHandler,
    ImageMediaHandler,
    AudioMediaHandler,
    DocumentMediaHandler,
    TextMediaHandler,
    descrever_imagem_com_visao,
    descrever_gif_com_visao,
    transcrever_audio_com_whisper,
    extrair_e_resumir_pdf,
)

__all__ = [
    "MediaPipeline",
    "BaseMediaHandler",
    "normalizar_mensagem_para_texto",
    "default_media_pipeline",
    "descrever_imagem_com_visao",
    "descrever_gif_com_visao",
    "transcrever_audio_com_whisper",
    "extrair_e_resumir_pdf",
]


class MediaPipeline:
    """
    Pipeline orquestrador de mídias do WhatsApp.
    Permite extensibilidade aberta para novos formatos e tipos de mídia (OCP).
    """

    def __init__(self, handlers: list[BaseMediaHandler] | None = None) -> None:
        self._handlers: list[BaseMediaHandler] = handlers if handlers is not None else []

    def register(self, handler: BaseMediaHandler, index: int | None = None) -> None:
        """Registra um novo handler de mídia no pipeline."""
        if index is not None:
            self._handlers.insert(index, handler)
        else:
            self._handlers.append(handler)
        logger.debug(f"[MEDIA PIPELINE] Handler '{handler.nome}' registrado.")

    async def process(self, message: schemas.UazapiMessage | None) -> str:
        """
        Executa a cadeia de estratégias até encontrar o handler adequado.
        """
        if not message:
            return "[Mensagem vazia]"

        tipo = (message.messageType or "").lower()
        texto = (message.text or "").strip()
        file_url = (message.fileURL or "").lower()

        # Extrai dicionário de content com segurança defensiva
        content_dict: dict[str, Any] = {}
        if isinstance(message.content, dict):
            content_dict = message.content
        elif isinstance(message.content, str):
            try:
                content_dict = json.loads(message.content)
            except Exception:
                content_dict = {}

        legenda = (
            texto
            or content_dict.get("caption")
            or content_dict.get("text")
            or content_dict.get("conversation")
            or ""
        )

        # Itera pelas estratégias registradas
        for handler in self._handlers:
            if handler.can_handle(message, content_dict, tipo, file_url):
                try:
                    return await handler.handle(message, content_dict, legenda)
                except Exception as err:
                    logger.error(f"[MEDIA PIPELINE ERRO] Falha no handler {handler.nome}: {err}")
                    # Continua para o próximo handler ou fallback

        if legenda:
            return legenda

        return "[Mensagem sem conteúdo de texto legível]"


# Instância padrão configurada com os handlers canônicos do sistema
default_media_pipeline = MediaPipeline([
    GifOrVideoHandler(),
    ImageMediaHandler(),
    AudioMediaHandler(),
    DocumentMediaHandler(),
    TextMediaHandler(),
])


async def normalizar_mensagem_para_texto(message: schemas.UazapiMessage | None) -> str:
    """
    Função de compatibilidade que delega ao pipeline padrão de estratégias de mídia.
    """
    return await default_media_pipeline.process(message)
