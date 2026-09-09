import os
import httpx

# Lê as variáveis de ambiente
UAZAPI_URL = os.getenv("UAZAPI_URL", "https://inteligentte.uazapi.com")
UAZAPI_TOKEN = os.getenv("UAZAPI_TOKEN")

async def enviar_mensagem(telefone: str, texto: str, delay: int = 1500) -> dict:
    """
    Envia uma mensagem de texto para o número fornecido via Uazapi.
    Baseado na documentação (via n8n) do usuário.
    """
    if not UAZAPI_TOKEN:
        print("⚠️ ERRO: UAZAPI_TOKEN não está configurado no arquivo .env!")
        return {"status": "erro", "detalhe": "Token não configurado"}
        
    url = f"{UAZAPI_URL}/send/text"
    
    headers = {
        "content-Type": "application/json",
        "token": UAZAPI_TOKEN
    }
    
    body = {
        "number": telefone,
        "text": texto,
        "delay": str(delay)
    }
    
    try:
        # Usamos timeout de 15 segundos para não travar a API se a Uazapi estiver lenta
        async with httpx.AsyncClient(timeout=15.0) as client:
            resposta = await client.post(url, headers=headers, json=body)
            
            # Levanta um erro se o status HTTP não for de sucesso (200, 201)
            resposta.raise_for_status()
            
            dados = resposta.json()
            print(f"🚀 [UAZAPI SEND] Mensagem enviada para {telefone} com sucesso!")
            return {"status": "sucesso", "dados": dados}
            
    except httpx.HTTPStatusError as e:
        erro = e.response.text
        print(f"❌ [UAZAPI SEND] Erro da API ({e.response.status_code}): {erro}")
        return {"status": "erro", "detalhe": erro}
    except Exception as e:
        print(f"❌ [UAZAPI SEND] Falha na comunicação: {str(e)}")
        return {"status": "erro", "detalhe": str(e)}
