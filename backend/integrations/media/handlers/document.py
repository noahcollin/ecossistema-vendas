"""
Handler de Mídia especializado em documentos PDF.
Extrai texto selecionável com pypdf e realiza síntese executiva
comercial via gpt-4o-mini para documentos extensos.
"""

import io
import base64
from typing import Any
import pypdf
from core.logger import logger
from core.config import settings
from core.openai_client import openai_client
from integrations.media.prompts import PROMPT_RESUMO_PDF
from integrations.uazapi.client import baixar_arquivo
import schemas
from .base import BaseMediaHandler


async def extrair_e_resumir_pdf(base64_pdf: str) -> str:
    """
    Decodifica o base64 do documento PDF e extrai o texto com pypdf.
    Se o documento for longo, gera um resumo executivo objetivo com IA.
    """
    try:
        logger.info("[MEDIA PDF] 📄 Decodificando e extraindo texto do PDF...")
        pdf_bytes = base64.b64decode(base64_pdf)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        
        num_paginas = len(reader.pages)
        textos_paginas = []
        for i, pagina in enumerate(reader.pages[:8]):  # Lê até as primeiras 8 páginas
            t = pagina.extract_text()
            if t:
                textos_paginas.append(t.strip())
                
        texto_completo = "\n".join(textos_paginas).strip()
        
        if not texto_completo:
            logger.warning("[MEDIA PDF] PDF sem texto selecionável (documento digitalizado).")
            return "Documento PDF recebido, porém as páginas parecem ser imagens escaneadas sem texto selecionável legível."
            
        logger.info(f"[MEDIA PDF] Texto extraído com sucesso ({len(texto_completo)} caracteres em {num_paginas} páginas)")
        
        # Se for um documento curto (< 400 caracteres), entrega o texto direto
        if len(texto_completo) <= 400:
            return texto_completo
            
        # Se for um documento mais extenso, usa o modelo de análise para fazer a síntese comercial
        logger.info(f"[MEDIA PDF] 🤖 Sintetizando pontos comerciais do PDF com {settings.MODEL_ANALYZER}...")
        
        resposta = await openai_client.chat.completions.create(
            model=settings.MODEL_ANALYZER,
            messages=[
                {"role": "system", "content": PROMPT_RESUMO_PDF},
                {"role": "user", "content": texto_completo[:4000]}
            ],
            max_tokens=150,
            temperature=0.3
        )
        
        resumo = resposta.choices[0].message.content.strip()
        logger.info(f"[MEDIA PDF] ✅ Resumo do PDF concluído: {resumo}")
        return resumo
        
    except Exception as e:
        logger.error(f"[MEDIA PDF ERRO] ❌ Falha ao processar PDF: {e}")
        return "Documento PDF enviado pelo cliente (não foi possível extrair o texto automaticamente)."


async def processar_documento(message: schemas.UazapiMessage, content_dict: dict[str, Any], legenda: str) -> str:
    """
    Coordena o download e o processamento de documentos PDF.
    Aproveita metadados (nome do arquivo) e base64 embutidos no payload antes de baixar via API.
    """
    msg_id = message.messageid or message.id or ""
    logger.info(f"[MEDIA] 📄 Documento detectado (tipo: {message.messageType}, ID: {msg_id})")
    
    # 1. Extrai o nome do arquivo a partir de content_dict ou da mensagem
    nome_arquivo = ""
    base64_payload = None
    if isinstance(content_dict, dict):
        nome_arquivo = content_dict.get("fileName") or content_dict.get("title") or ""
        base64_payload = content_dict.get("base64Data") or content_dict.get("base64")
        
    if not nome_arquivo:
        nome_arquivo = getattr(message, "fileName", "") or ""
        
    rotulo_doc = f" ({nome_arquivo})" if nome_arquivo else ""
    
    # 2. Obtém o base64 (embutido ou baixado via Uazapi)
    base64_data = base64_payload
    if not base64_data and msg_id:
        dados_arquivo = await baixar_arquivo(msg_id)
        base64_data = dados_arquivo.get("base64Data")
        
    if base64_data:
        conteudo_pdf = await extrair_e_resumir_pdf(base64_data)
        if legenda:
            return f"[DOCUMENTO PDF{rotulo_doc} DO CLIENTE: {conteudo_pdf}. Legenda: '{legenda}']"
        return f"[DOCUMENTO PDF{rotulo_doc} DO CLIENTE: {conteudo_pdf}]"
        
    if legenda:
        return f"[DOCUMENTO PDF{rotulo_doc} ENVIADO PELO CLIENTE com a legenda: '{legenda}']"
    return f"[DOCUMENTO PDF{rotulo_doc} ENVIADO PELO CLIENTE]"


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
