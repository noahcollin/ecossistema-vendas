"""
Processador especializado em GIFs animados, memes de reação e vídeos.
Prioriza o frame JPEGThumbnail nativo da mensagem (Zero Latência) antes de tentar download.
"""

from openai import AsyncOpenAI
from core.logger import logger
from services.media.prompts import PROMPT_GIF
from services.uazapi_service import baixar_arquivo

openai_client = AsyncOpenAI()

async def descrever_gif_com_visao(url_ou_base64: str, mimetype: str = "image/jpeg") -> str:
    """
    Invoca o gpt-4o-mini Vision com prompt especializado em identificar memes e emoções.
    """
    try:
        if url_ou_base64.startswith("http://") or url_ou_base64.startswith("https://"):
            imagem_content = {"url": url_ou_base64, "detail": "low"}
        elif url_ou_base64.startswith("data:"):
            imagem_content = {"url": url_ou_base64, "detail": "low"}
        else:
            imagem_content = {"url": f"data:{mimetype};base64,{url_ou_base64}", "detail": "low"}

        logger.info("[MEDIA GIF] 🎬 Analisando GIF/animação com gpt-4o-mini Vision...")
        
        resposta = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT_GIF},
                        {"type": "image_url", "image_url": imagem_content}
                    ]
                }
            ],
            max_tokens=120,
            temperature=0.3
        )
        
        descricao = resposta.choices[0].message.content.strip()
        logger.info(f"[MEDIA GIF] ✅ GIF interpretado: {descricao}")
        return descricao
    except Exception as e:
        logger.error(f"[MEDIA GIF ERRO] Falha na interpretação do GIF: {e}")
        return "Animação/GIF enviado pelo cliente (não foi possível extrair a reação visual)."

async def processar_gif_ou_video(message, content_dict: dict, legenda: str, eh_gif: bool = True) -> str:
    """
    Coordena o processamento de animações e vídeos.
    Extrai o JPEGThumbnail embutido se disponível, ou solicita download na Uazapi.
    """
    msg_id = message.messageid or message.id or ""
    file_url = message.fileURL or ""
    rotulo = "GIF/ANIMAÇÃO ENVIADA PELO CLIENTE" if eh_gif else "VÍDEO ENVIADO PELO CLIENTE"
    
    logger.info(f"[MEDIA] 🎬 {rotulo} detectado (tipo: {message.messageType}, ID: {msg_id})")
    
    # 1. Tenta extrair o JPEGThumbnail embutido no payload (Zero Latência)
    thumbnail_b64 = (
        content_dict.get("JPEGThumbnail")
        or content_dict.get("jpegThumbnail")
        or content_dict.get("thumbnail")
        or getattr(message, "thumbnail", None)
    )
    
    origem_midia = None
    mimetype_midia = "image/jpeg"
    
    if thumbnail_b64:
        logger.info("[MEDIA GIF] ⚡ Thumbnail nativo encontrado no payload da mensagem!")
        origem_midia = thumbnail_b64
    else:
        # 2. Fallback: solicita download via API da Uazapi
        logger.info(f"[MEDIA GIF] 🔍 Thumbnail não embutido. Solicitando download da mensagem {msg_id} à Uazapi...")
        dados_arquivo = {}
        if msg_id:
            dados_arquivo = await baixar_arquivo(msg_id)
            
        thumb_uazapi = dados_arquivo.get("thumbnail")
        base64_data = dados_arquivo.get("base64Data")
        download_url = dados_arquivo.get("fileURL") or file_url
        mimetype_arquivo = dados_arquivo.get("mimetype") or ""
        
        if thumb_uazapi:
            origem_midia = thumb_uazapi
            mimetype_midia = "image/jpeg"
        elif "gif" in mimetype_arquivo.lower() or download_url.lower().endswith(".gif"):
            origem_midia = base64_data if base64_data else download_url
            mimetype_midia = "image/gif"
        elif base64_data and not base64_data.startswith("AAAA"):
            origem_midia = base64_data
            mimetype_midia = mimetype_arquivo or "image/jpeg"
            
    if origem_midia:
        descricao = await descrever_gif_com_visao(origem_midia, mimetype=mimetype_midia)
        if legenda:
            return f"[{rotulo}: {descricao}. Legenda do cliente: '{legenda}']"
        return f"[{rotulo}: {descricao}]"
    else:
        if legenda:
            return f"[{rotulo} com a legenda: '{legenda}']"
        return f"[{rotulo}]"
