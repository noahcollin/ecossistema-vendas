"""
Módulo de Fachada de Retrocompatibilidade para o pacote services.media.
Permite que chamadas legadas como `from services import media_service` continuem
funcionando de forma 100% transparente sem quebrar referências externas.
"""

from services.media import (
    normalizar_mensagem_para_texto,
    descrever_imagem_com_visao,
    descrever_gif_com_visao,
    transcrever_audio_com_whisper,
    extrair_e_resumir_pdf,
)
from services.media.prompts import (
    PROMPT_OLHOS_DO_VENDEDOR,
    PROMPT_GIF,
    PROMPT_RESUMO_PDF,
)
from services.uazapi_service import (
    baixar_arquivo as baixar_arquivo_uazapi,
    baixar_arquivo,
)

__all__ = [
    "normalizar_mensagem_para_texto",
    "descrever_imagem_com_visao",
    "descrever_gif_com_visao",
    "transcrever_audio_com_whisper",
    "extrair_e_resumir_pdf",
    "baixar_arquivo_uazapi",
    "baixar_arquivo",
    "PROMPT_OLHOS_DO_VENDEDOR",
    "PROMPT_GIF",
    "PROMPT_RESUMO_PDF",
]
