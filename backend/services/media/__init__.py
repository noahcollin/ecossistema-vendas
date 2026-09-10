"""
Pacote Modular de Processamento e Inteligência de Mídias.
Centraliza o roteamento de mídias do WhatsApp para texto comercial mastigado.
"""

import json
import schemas
from core.logger import logger

from services.media.handlers.vision_handler import processar_imagem, descrever_imagem_com_visao
from services.media.handlers.gif_handler import processar_gif_ou_video, descrever_gif_com_visao
from services.media.handlers.audio_handler import processar_audio, transcrever_audio_com_whisper
from services.media.handlers.pdf_handler import processar_documento, extrair_e_resumir_pdf

__all__ = [
    "normalizar_mensagem_para_texto",
    "descrever_imagem_com_visao",
    "descrever_gif_com_visao",
    "transcrever_audio_com_whisper",
    "extrair_e_resumir_pdf",
]

async def normalizar_mensagem_para_texto(message: schemas.UazapiMessage | None) -> str:
    """
    Dispatcher do Pipeline de Mídias:
    Analisa o tipo de mensagem da Uazapi (texto, foto, áudio, pdf, gif, vídeo)
    e delega para o handler especializado correspondente.
    """
    if not message:
        return "[Mensagem vazia]"
        
    tipo = (message.messageType or "").lower()
    texto = (message.text or "").strip()
    file_url = (message.fileURL or "").lower()
    
    # Extrai o dicionário de content com segurança
    content_dict = {}
    if isinstance(message.content, dict):
        content_dict = message.content
    elif isinstance(message.content, str):
        try:
            content_dict = json.loads(message.content)
        except Exception:
            content_dict = {}
            
    legenda = texto or content_dict.get("caption") or ""

    # 1. Se for GIF / ANIMAÇÃO / VÍDEO
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
    if eh_gif or eh_video:
        return await processar_gif_ou_video(message, content_dict, legenda, eh_gif=eh_gif)

    # 2. Se for IMAGEM ou FIGURINHA
    if "image" in tipo or "sticker" in tipo or any(ext in file_url for ext in [".jpg", ".jpeg", ".png", ".webp"]):
        return await processar_imagem(message, content_dict, legenda)

    # 3. Se for ÁUDIO ou NOTA DE VOZ (PTT)
    if "audio" in tipo or "voice" in tipo or "ptt" in tipo or any(ext in file_url for ext in [".mp3", ".ogg", ".opus", ".m4a", ".wav"]):
        return await processar_audio(message, content_dict)

    # 4. Se for DOCUMENTO / PDF
    if "document" in tipo or ".pdf" in file_url:
        return await processar_documento(message, content_dict, legenda)

    # 5. Mensagem de Texto Normal
    if legenda:
        return legenda

    return "[Mensagem sem conteúdo de texto legível]"
