"""
Contrato base para Handlers do Pipeline de Mídias (Strategy Pattern / OCP).
Permite plugar novos tipos de mídias (localização, contato, reações, novas extensões)
sem violar o princípio Aberto/Fechado.
"""

from abc import ABC, abstractmethod
from typing import Any
import schemas


class BaseMediaHandler(ABC):
    """
    Interface abstrata que todo handler de mídia deve implementar.
    """

    @property
    def nome(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def can_handle(
        self,
        message: schemas.UazapiMessage,
        content_dict: dict[str, Any],
        tipo: str,
        file_url: str
    ) -> bool:
        """
        Avalia se a mensagem deve ser processada por este handler.
        """
        pass

    @abstractmethod
    async def handle(
        self,
        message: schemas.UazapiMessage,
        content_dict: dict[str, Any],
        legenda: str
    ) -> str:
        """
        Executa a transformação da mídia em representação textual comercial.
        """
        pass
