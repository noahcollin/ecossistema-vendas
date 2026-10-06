"""
Módulo Centralizador de Handlers do Pipeline de Mídias (Strategy Pattern / OCP).
Re-exporta todas as classes de estratégias e funções de processamento.
"""

from .base import BaseMediaHandler
from .image import ImageMediaHandler, descrever_imagem_com_visao, processar_imagem
from .audio import AudioMediaHandler, transcrever_audio_com_whisper, processar_audio
from .document import DocumentMediaHandler, extrair_e_resumir_pdf, processar_documento
from .video_gif import GifOrVideoHandler, descrever_gif_com_visao, processar_gif_ou_video
from .text import TextMediaHandler
from integrations.media.vision_client import executar_analise_visual

__all__ = [
    # Handlers (Strategy Pattern)
    "BaseMediaHandler",
    "ImageMediaHandler",
    "AudioMediaHandler",
    "DocumentMediaHandler",
    "GifOrVideoHandler",
    "TextMediaHandler",
    # Funções de Processamento e Análise
    "descrever_imagem_com_visao",
    "processar_imagem",
    "transcrever_audio_com_whisper",
    "processar_audio",
    "extrair_e_resumir_pdf",
    "processar_documento",
    "descrever_gif_com_visao",
    "processar_gif_ou_video",
    "executar_analise_visual",
]
