"""
Processador especializado em imagens estáticas e figurinhas (stickers).
Utiliza gpt-4o-mini Vision em modo detail: "low" para descrição concisa e econômica.
"""

from core.logger import logger
from integrations.media.prompts import PROMPT_OLHOS_DO_VENDEDOR
from integrations.media.handlers.base_vision import executar_analise_visual
from integrations.uazapi.client import baixar_arquivo

async def descrever_imagem_com_visao(url_ou_base64: str, mimetype: str = "image/jpeg") -> str:
    """
    Invoca a IA com visão computacional para interpretar uma imagem estática ou figurinha.
    """
    logger.info("[MEDIA VISION] 👁️ Analisando imagem com visão computacional...")
    descricao = await executar_analise_visual(
        url_ou_base64=url_ou_base64,
        prompt_instrucao=PROMPT_OLHOS_DO_VENDEDOR,
        mimetype=mimetype,
        max_tokens=120,
        temperature=0.3,
        fallback_mensagem="Foto/Imagem enviada pelo cliente (não foi possível extrair os detalhes visuais)."
    )
    logger.info(f"[MEDIA VISION] ✅ Imagem interpretada: {descricao}")
    return descricao

async def processar_imagem(message, content_dict: dict, legenda: str) -> str:
    """
    Coordena o fluxo de obtenção da imagem/figurinha e formatação do texto final.
    Aproveita JPEGThumbnail embutido no payload (Zero Latência) antes de baixar via API.
    """
    msg_id = message.messageid or message.id or ""
    file_url = message.fileURL or ""
    
    logger.info(f"[MEDIA] 📸 Mensagem com Imagem/Sticker detectada (tipo: {message.messageType}, ID: {msg_id})")
    
    # 1. Tenta extrair o JPEGThumbnail embutido no payload (Zero Latência)
    thumbnail_b64 = None
    if isinstance(content_dict, dict):
        thumbnail_b64 = (
            content_dict.get("JPEGThumbnail")
            or content_dict.get("jpegThumbnail")
            or content_dict.get("thumbnail")
            or getattr(message, "thumbnail", None)
        )
        
    origem_imagem = None
    mimetype = "image/jpeg"
    
    if thumbnail_b64:
        logger.info("[MEDIA VISION] ⚡ Thumbnail nativo encontrado no payload da imagem!")
        origem_imagem = thumbnail_b64
    else:
        # 2. Fallback: baixa o arquivo completo via Uazapi
        dados_arquivo = {}
        if msg_id:
            dados_arquivo = await baixar_arquivo(msg_id)
            
        base64_data = dados_arquivo.get("base64Data")
        download_url = dados_arquivo.get("fileURL") or file_url
        mimetype = dados_arquivo.get("mimetype") or (content_dict.get("mimetype") if isinstance(content_dict, dict) else None) or "image/jpeg"
        origem_imagem = base64_data if base64_data else download_url
    
    if origem_imagem:
        descricao_visual = await descrever_imagem_com_visao(origem_imagem, mimetype=mimetype)
        if legenda:
            return f"[IMAGEM ENVIADA PELO CLIENTE: {descricao_visual}. Legenda do cliente: '{legenda}']"
        return f"[IMAGEM ENVIADA PELO CLIENTE: {descricao_visual}]"
    else:
        if legenda:
            return f"[IMAGEM ENVIADA PELO CLIENTE com a legenda: '{legenda}']"
        return "[IMAGEM ENVIADA PELO CLIENTE]"
