"""
Processador especializado em documentos PDF.
Extrai texto selecionável com pypdf e realiza síntese executiva
comercial via gpt-4o-mini para documentos extensos.
"""

import io
import base64
import pypdf
from openai import AsyncOpenAI
from core.logger import logger
from services.media.prompts import PROMPT_RESUMO_PDF
from services.uazapi_service import baixar_arquivo

openai_client = AsyncOpenAI()

async def extrair_e_resumir_pdf(base64_pdf: str) -> str:
    """
    Decodifica o base64 do documento PDF e extrai o texto com pypdf.
    Se o documento for longo, gera um resumo executivo objetivo com gpt-4o-mini.
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
            
        # Se for um documento mais extenso, usa gpt-4o-mini para fazer a síntese comercial
        logger.info("[MEDIA PDF] 🤖 Sintetizando pontos comerciais do PDF com gpt-4o-mini...")
        
        resposta = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
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

async def processar_documento(message, content_dict: dict, legenda: str) -> str:
    """
    Coordena o download e o processamento de documentos PDF.
    """
    msg_id = message.messageid or message.id or ""
    logger.info(f"[MEDIA] 📄 Documento detectado (tipo: {message.messageType}, ID: {msg_id})")
    
    dados_arquivo = {}
    if msg_id:
        dados_arquivo = await baixar_arquivo(msg_id)
        
    base64_data = dados_arquivo.get("base64Data")
    if base64_data:
        conteudo_pdf = await extrair_e_resumir_pdf(base64_data)
        if legenda:
            return f"[DOCUMENTO PDF DO CLIENTE: {conteudo_pdf}. Legenda: '{legenda}']"
        return f"[DOCUMENTO PDF DO CLIENTE: {conteudo_pdf}]"
        
    if legenda:
        return f"[DOCUMENTO PDF ENVIADO PELO CLIENTE com a legenda: '{legenda}']"
    return "[DOCUMENTO PDF ENVIADO PELO CLIENTE]"
