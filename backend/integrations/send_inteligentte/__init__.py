"""
Integração Oficial com o Send Inteligentte (Meta Cloud API Gateway).
"""

from .client import (
    get_send_client,
    close_send_client,
    buscar_eventos_send,
    enviar_mensagem_send,
    solicitar_handover_send,
    baixar_midia_send,
    limpar_telefone_send,
)

__all__ = [
    "get_send_client",
    "close_send_client",
    "buscar_eventos_send",
    "enviar_mensagem_send",
    "solicitar_handover_send",
    "baixar_midia_send",
    "limpar_telefone_send",
]

