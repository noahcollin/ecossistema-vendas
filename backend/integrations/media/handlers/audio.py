"""
Handler de Mídia especializado em áudios e mensagens de voz (PTT).
Utiliza OpenAI Whisper-1 para transcrição de alta fidelidade em português
com aproveitamento da transcrição nativa da Uazapi quando disponível.
"""

import io
import base64
from typing import Any
from core.logger import logger
from core.openai_client import openai_client
from core.config import settings
from integrations.uazapi.client import baixar_arquivo
import schemas
from .base import BaseMediaHandler


async def transcrever_audio_com_whisper(base64_audio: str) -> str:
    """
    Decodifica o base64 do áudio e envia para o Whisper da OpenAI.
    """
    try:
        logger.info("[MEDIA WHISPER] 🎙️ Decodificando áudio e enviando para Whisper...")
        audio_bytes = base64.b64decode(base64_audio)
        
        buffer_audio = io.BytesIO(audio_bytes)
        buffer_audio.name = "audio.mp3"
        
        transcricao = await openai_client.audio.transcriptions.create(
            model=settings.MODEL_WHISPER,
            file=buffer_audio,
            language="pt"
        )
        
        texto_transcrito = transcricao.text.strip()
        logger.info(f"[MEDIA WHISPER] ✅ Áudio transcrito com sucesso: '{texto_transcrito}'")
        return texto_transcrito
    except Exception as e:
        logger.error(f"[MEDIA WHISPER ERRO] ❌ Falha ao transcrever áudio com Whisper: {e}")
        return ""


async def processar_audio(message: schemas.UazapiMessage, content_dict: dict[str, Any]) -> str:
    """
    Coordena o download e a transcrição da mensagem de voz/áudio.
    Aproveita transcrição ou áudio embutido no payload (Zero Latência) antes de baixar via API.
    """
    msg_id = message.messageid or message.id or ""
    logger.info(f"[MEDIA] 🎙️ Áudio detectado (tipo: {message.messageType}, ID: {msg_id})")
    
    # 0º: Checa se a transcrição nativa já veio no payload da mensagem
    if isinstance(content_dict, dict):
        transcricao_payload = content_dict.get("transcription") or content_dict.get("text")
        if transcricao_payload and transcricao_payload.strip():
            logger.info(f"[MEDIA WHISPER] ⚡ Transcrição nativa encontrada no payload: '{transcricao_payload.strip()}'")
            return f"[ÁUDIO/MENSAGEM DE VOZ DO CLIENTE: '{transcricao_payload.strip()}']"
            
    dados_arquivo = {}
    if msg_id:
        dados_arquivo = await baixar_arquivo(msg_id, generate_mp3=True)
        
    # 1º: Checa se a Uazapi enviou transcrição na resposta do download
    transcricao_uazapi = dados_arquivo.get("transcription")
    if transcricao_uazapi and transcricao_uazapi.strip():
        logger.info(f"[MEDIA WHISPER] Transcrição nativa da Uazapi aproveitada: '{transcricao_uazapi}'")
        return f"[ÁUDIO/MENSAGEM DE VOZ DO CLIENTE: '{transcricao_uazapi.strip()}']"
        
    # 2º: Transcreve via OpenAI Whisper
    base64_data = dados_arquivo.get("base64Data") or (content_dict.get("base64Data") if isinstance(content_dict, dict) else None)
    if base64_data:
        transcricao_whisper = await transcrever_audio_com_whisper(base64_data)
        if transcricao_whisper:
            return f"[ÁUDIO/MENSAGEM DE VOZ DO CLIENTE: '{transcricao_whisper}']"

    return "[ÁUDIO INAUDÍVEL: O cliente enviou uma mensagem de áudio, mas ela veio sem som legível, muda ou com muito ruído. Peça gentilmente para ele digitar ou mandar outro áudio.]"


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
