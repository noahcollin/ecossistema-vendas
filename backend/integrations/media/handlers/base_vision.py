"""
Módulo base para chamadas visuais aos modelos de IA (OpenAI Vision).
Centraliza o preparo de payloads de imagem/thumbnail, tratamento de URLs/base64,
configurações de modelo e tratamento de erros de visão.
"""

from core.logger import logger
from core.config import settings
from core.openai_client import openai_client


async def executar_analise_visual(
    url_ou_base64: str,
    prompt_instrucao: str,
    model: str | None = None,
    mimetype: str = "image/jpeg",
    max_tokens: int = 120,
    temperature: float = 0.3,
    fallback_mensagem: str = "Mídia visual enviada pelo cliente."
) -> str:
    """
    Executa a chamada visual ao modelo de visão configurado (ex: settings.MODEL_ANALYZER)
    com detail: 'low' para máxima velocidade e economia de tokens.
    """
    try:
        modelo_final = model or settings.MODEL_ANALYZER

        if url_ou_base64.startswith("http://") or url_ou_base64.startswith("https://"):
            imagem_content = {"url": url_ou_base64, "detail": "low"}
        elif url_ou_base64.startswith("data:"):
            imagem_content = {"url": url_ou_base64, "detail": "low"}
        else:
            imagem_content = {"url": f"data:{mimetype};base64,{url_ou_base64}", "detail": "low"}

        resposta = await openai_client.chat.completions.create(
            model=modelo_final,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_instrucao},
                        {"type": "image_url", "image_url": imagem_content}
                    ]
                }
            ],
            max_tokens=max_tokens,
            temperature=temperature
        )

        descricao = resposta.choices[0].message.content.strip()
        return descricao
    except Exception as e:
        logger.error(f"[BASE VISION ERRO] Falha na interpretação visual: {e}")
        return fallback_mensagem
