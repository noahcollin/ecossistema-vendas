"""
Implementação concreta do gateway do WhatsApp utilizando a API da Uazapi.
Em conformidade com WhatsAppGatewayProtocol.
"""

from typing import Any
from core.protocols import WhatsAppGatewayProtocol
from integrations.uazapi import client


class UazapiGateway:
    """Gateway de integração com o serviço de WhatsApp via Uazapi."""

    async def enviar_presenca(
        self,
        telefone: str,
        presenca: str = "composing",
        delay_ms: int = 15000
    ) -> dict[str, Any]:
        return await client.enviar_presenca(
            telefone=telefone,
            presenca=presenca,
            delay_ms=delay_ms
        )

    async def enviar_mensagem(
        self,
        telefone: str,
        texto: str,
        delay_ms: int = 2000,
        max_retries: int = 2
    ) -> dict[str, Any]:
        return await client.enviar_mensagem(
            telefone=telefone,
            texto=texto,
            delay_ms=delay_ms,
            max_retries=max_retries
        )

    async def enviar_mensagem_humanizada(
        self,
        telefone: str,
        texto_bruto: str,
        delay_base_ms: int = 1500,
        simular_digitacao: bool = True,
        intervalo_entre_baloes: float = 1.8
    ) -> tuple[list[str], bool]:
        return await client.enviar_mensagem_humanizada(
            telefone=telefone,
            texto_bruto=texto_bruto,
            delay_base_ms=delay_base_ms,
            simular_digitacao=simular_digitacao,
            intervalo_entre_baloes=intervalo_entre_baloes
        )

    async def baixar_arquivo(
        self,
        message_id: str,
        generate_mp3: bool = False
    ) -> dict[str, Any]:
        return await client.baixar_arquivo(
            message_id=message_id,
            generate_mp3=generate_mp3
        )


# Instância canônica singleton padrão
default_uazapi_gateway = UazapiGateway()
