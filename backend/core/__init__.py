"""
Núcleo Transversal e Infraestrutura do Ecossistema de Vendas (Core).
Fachada central para configurações, banco de dados, logging, contratos, segurança e utilitários.
"""

from .config import settings
from .logger import logger
from .database import engine, Base, AsyncSessionLocal, get_db
from .openai_client import openai_client
from .protocols import WhatsAppGatewayProtocol, CacheBufferProtocol
from .temporal.business_hours import BusinessHoursPolicy
from .exceptions import (
    AppException,
    DomainException,
    LeadNotFoundError,
    LeadOptedOutError,
    InvalidPhoneNumberError,
    TransbordoStateError,
    InfrastructureException,
    BufferOperationError,
    ExternalGatewayError,
    OpenAIQuotaExhaustedError,
)
from .security import validar_admin_api_key, const_time_compare, SecurityHeadersMiddleware
from .utils import (
    mascarar_telefone,
    mascarar_nome,
    normalizar_telefone,
    higienizar_nome_perfil,
    dividir_mensagens_whatsapp,
)

__all__ = [
    # Config, Observabilidade & Segurança
    "settings",
    "logger",
    "validar_admin_api_key",
    "const_time_compare",
    "SecurityHeadersMiddleware",
    # Banco de Dados
    "engine",
    "Base",
    "AsyncSessionLocal",
    "get_db",
    # IA & Contratos
    "openai_client",
    "WhatsAppGatewayProtocol",
    "CacheBufferProtocol",
    # Políticas Temporais
    "BusinessHoursPolicy",
    # Exceções
    "AppException",
    "DomainException",
    "LeadNotFoundError",
    "LeadOptedOutError",
    "InvalidPhoneNumberError",
    "TransbordoStateError",
    "InfrastructureException",
    "BufferOperationError",
    "ExternalGatewayError",
    "OpenAIQuotaExhaustedError",
    # Utilitários
    "mascarar_telefone",
    "mascarar_nome",
    "normalizar_telefone",
    "higienizar_nome_perfil",
    "dividir_mensagens_whatsapp",
]
