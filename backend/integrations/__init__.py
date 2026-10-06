"""
Camada de Integrações Externas (Hexagonal Architecture / Adapters & Gateways).
Isola clientes de terceiros, drivers de mensageria e infraestrutura externa.
"""

from .transbordo_notifier import TransbordoNotifier

__all__ = ["TransbordoNotifier"]

