"""
Esquemas Pydantic para Ingestão de Payloads de Webhook do WhatsApp (Uazapi).
"""

from typing import Optional, Any
from pydantic import BaseModel, ConfigDict


class UazapiChat(BaseModel):
    """Metadados do chat / contato recebido via WhatsApp."""
    name: Optional[str] = None
    phone: str
    isGroup: Optional[bool] = False


class UazapiMessage(BaseModel):
    """Corpo da mensagem do WhatsApp (texto, mídia, remetente)."""
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    messageid: Optional[str] = None
    fromMe: Optional[bool] = False
    isGroup: Optional[bool] = False
    text: Optional[str] = None
    senderName: Optional[str] = None
    messageType: Optional[str] = None
    fileURL: Optional[str] = None
    content: Optional[Any] = None
    wasSentByApi: Optional[bool] = False


class UazapiPayload(BaseModel):
    """Payload raiz do evento de webhook recebido da Uazapi."""
    model_config = ConfigDict(extra="allow")

    event: Optional[str] = None
    instanceName: Optional[str] = None
    chat: Optional[UazapiChat] = None
    message: Optional[UazapiMessage] = None
