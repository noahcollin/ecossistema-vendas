"""
Testes Unitários do Pipeline de Mídias (Strategy Pattern e Open-Closed Principle).
"""

from typing import Any
import pytest
import schemas
from integrations.media import MediaPipeline, BaseMediaHandler, default_media_pipeline


class CustomLocationHandler(BaseMediaHandler):
    """Handler plugado dinamicamente para mensagens de geolocalização (OCP)."""

    def can_handle(self, message: schemas.UazapiMessage, content_dict: dict[str, Any], tipo: str, file_url: str) -> bool:
        return tipo == "location" or "latitude" in content_dict

    async def handle(self, message: schemas.UazapiMessage, content_dict: dict[str, Any], legenda: str) -> str:
        lat = content_dict.get("latitude", "0.0")
        lng = content_dict.get("longitude", "0.0")
        return f"[LOCALIZAÇÃO ENVIADA PELO CLIENTE: Lat {lat}, Lng {lng}]"


@pytest.mark.asyncio
async def test_media_pipeline_plain_text():
    """Valida o processamento de mensagens de texto comuns."""
    msg = schemas.UazapiMessage(messageType="conversation", text="Gostaria de um orçamento solar")
    resultado = await default_media_pipeline.process(msg)
    assert resultado == "Gostaria de um orçamento solar"


@pytest.mark.asyncio
async def test_media_pipeline_empty_message():
    """Valida mensagem nula."""
    resultado = await default_media_pipeline.process(None)
    assert resultado == "[Mensagem vazia]"


@pytest.mark.asyncio
async def test_media_pipeline_ocp_extensibility():
    """Valida que novos tipos de mídia podem ser plugados sem alterar o código existente (OCP)."""
    pipeline = MediaPipeline()
    
    # Registra o novo handler customizado
    pipeline.register(CustomLocationHandler())

    msg_loc = schemas.UazapiMessage(
        messageType="location",
        content={"latitude": "-7.115", "longitude": "-34.863"}
    )

    resultado = await pipeline.process(msg_loc)
    assert resultado == "[LOCALIZAÇÃO ENVIADA PELO CLIENTE: Lat -7.115, Lng -34.863]"
