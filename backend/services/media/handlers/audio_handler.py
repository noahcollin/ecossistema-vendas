"""
Processador especializado em áudios e mensagens de voz (PTT).
Utiliza OpenAI Whisper-1 para transcrição de alta fidelidade em português
com aproveitamento da transcrição nativa da Uazapi quando disponível.
"""

import io
import base64
from openai import AsyncOpenAI
from core.logger import logger
from services.uazapi_service import baixar_arquivo

openai_client = AsyncOpenAI()

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
            model="whisper-1",
            file=buffer_audio,
            language="pt"
        )
        
        texto_transcrito = transcricao.text.strip()
        logger.info(f"[MEDIA WHISPER] ✅ Áudio transcrito com sucesso: '{texto_transcrito}'")
        return texto_transcrito
    except Exception as e:
        logger.error(f"[MEDIA WHISPER ERRO] ❌ Falha ao transcrever áudio com Whisper: {e}")
        return ""

async def processar_audio(message, content_dict: dict) -> str:
    """
    Coordena o download e a transcrição da mensagem de voz/áudio.
    """
    msg_id = message.messageid or message.id or ""
    logger.info(f"[MEDIA] 🎙️ Áudio detectado (tipo: {message.messageType}, ID: {msg_id})")
    
    dados_arquivo = {}
    if msg_id:
        dados_arquivo = await baixar_arquivo(msg_id, generate_mp3=True)
        
    # 1º: Checa se a Uazapi já enviou transcrição embutida
    transcricao_uazapi = dados_arquivo.get("transcription")
    if transcricao_uazapi and transcricao_uazapi.strip():
        logger.info(f"[MEDIA WHISPER] Transcrição nativa da Uazapi aproveitada: '{transcricao_uazapi}'")
        return f"[ÁUDIO/MENSAGEM DE VOZ DO CLIENTE: '{transcricao_uazapi.strip()}']"
        
    # 2º: Transcreve via OpenAI Whisper
    base64_data = dados_arquivo.get("base64Data")
    if base64_data:
        transcricao_whisper = await transcrever_audio_com_whisper(base64_data)
        if transcricao_whisper:
            return f"[ÁUDIO/MENSAGEM DE VOZ DO CLIENTE: '{transcricao_whisper}']"
            
    return "[ÁUDIO ENVIADO PELO CLIENTE: (Não foi possível transcrever com clareza)]"
