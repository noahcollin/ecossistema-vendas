import os
import httpx
from core.logger import logger

# Lê as variáveis de ambiente
UAZAPI_URL = os.getenv("UAZAPI_URL", "https://inteligentte.uazapi.com")
UAZAPI_TOKEN = os.getenv("UAZAPI_TOKEN")

async def enviar_presenca(telefone: str, presenca: str = "composing", delay_ms: int = 15000) -> dict:
    """
    Atualiza o status de presença da conversa no WhatsApp (ex: 'composing' para 'digitando...'
    ou 'recording' para 'gravando áudio...').
    """
    if not UAZAPI_TOKEN:
        logger.warning("[UAZAPI PRESENÇA] UAZAPI_TOKEN não está configurado.")
        return {"status": "erro", "detalhe": "Token não configurado"}

    url = f"{UAZAPI_URL}/message/presence"
    headers = {
        "Content-Type": "application/json",
        "token": UAZAPI_TOKEN
    }
    body = {
        "number": telefone,
        "presence": presenca,
        "delay": delay_ms
    }

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resposta = await client.post(url, headers=headers, json=body)
            resposta.raise_for_status()
            logger.info(f"[UAZAPI PRESENÇA] Status '{presenca}' enviado para {telefone}")
            return {"status": "sucesso"}
    except Exception as e:
        logger.warning(f"[UAZAPI PRESENÇA] Falha ao enviar presença '{presenca}': {e}")
        return {"status": "erro", "detalhe": str(e)}

async def enviar_mensagem(telefone: str, texto: str, delay_ms: int = 2000) -> dict:
    """
    Envia uma mensagem de texto para o número fornecido via Uazapi.
    Ativa automaticamente readchat=True para marcar a mensagem do lead como lida.
    """
    if not UAZAPI_TOKEN:
        logger.error("[UAZAPI SEND] UAZAPI_TOKEN não está configurado no arquivo .env!")
        return {"status": "erro", "detalhe": "Token não configurado"}
        
    url = f"{UAZAPI_URL}/send/text"
    headers = {
        "Content-Type": "application/json",
        "token": UAZAPI_TOKEN
    }
    
    body = {
        "number": telefone,
        "text": texto,
        "delay": str(delay_ms),
        "readchat": True,
        "readmessages": True
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resposta = await client.post(url, headers=headers, json=body)
            resposta.raise_for_status()
            
            dados = resposta.json()
            logger.info(f"[UAZAPI SEND] 🚀 Mensagem enviada para {telefone} com sucesso!")
            return {"status": "sucesso", "dados": dados}
            
    except httpx.HTTPStatusError as e:
        erro = e.response.text
        logger.error(f"[UAZAPI SEND] ❌ Erro da API Uazapi ({e.response.status_code}): {erro}")
        return {"status": "erro", "detalhe": erro}
    except Exception as e:
        logger.error(f"[UAZAPI SEND] ❌ Falha na comunicação: {str(e)}")
        return {"status": "erro", "detalhe": str(e)}

async def baixar_arquivo(message_id: str, generate_mp3: bool = False) -> dict:
    """
    Solicita o download do arquivo de uma mensagem diretamente via API da Uazapi.
    Retorna dicionário com base64Data, fileURL, mimetype, etc.
    """
    if not UAZAPI_TOKEN:
        logger.warning("[UAZAPI DOWNLOAD] UAZAPI_TOKEN não configurado para download de mídia.")
        return {}
        
    url = f"{UAZAPI_URL}/message/download"
    headers = {
        "Content-Type": "application/json",
        "token": UAZAPI_TOKEN
    }
    
    # Se o ID vier no formato "remetente:ID", extrai apenas o ID após os dois pontos
    id_limpo = message_id.split(":")[-1] if ":" in message_id else message_id
    
    body = {
        "id": id_limpo,
        "return_base64": True,
        "return_link": True
    }
    
    if generate_mp3:
        body["generate_mp3"] = True
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resposta = await client.post(url, headers=headers, json=body)
            if resposta.status_code == 200:
                dados = resposta.json()
                logger.info(f"[UAZAPI DOWNLOAD] 📥 Arquivo da mensagem {id_limpo} baixado com sucesso")
                return dados
            else:
                logger.warning(f"[UAZAPI DOWNLOAD] Falha ao baixar arquivo ({resposta.status_code}): {resposta.text}")
                return {}
    except Exception as e:
        logger.error(f"[UAZAPI DOWNLOAD ERRO] Falha ao contatar /message/download: {e}")
        return {}

# Alias para compatibilidade
baixar_arquivo_uazapi = baixar_arquivo

