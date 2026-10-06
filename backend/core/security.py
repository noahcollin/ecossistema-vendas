"""
Módulo de Segurança, Autenticação e Criptografia do Backend (Core Security).
Implementa validação de chaves de API e tokens Bearer com proteção contra timing attacks
e integração nativa com a documentação OpenAPI/Swagger do FastAPI.
"""

import hmac
from typing import Optional
from fastapi import Security, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader

from core.config import settings
from core.logger import logger

# Esquemas de segurança integrados ao OpenAPI / Swagger UI
bearer_scheme = HTTPBearer(auto_error=False, description="Token administrativo via header Authorization: Bearer <key>")
api_key_header_scheme = APIKeyHeader(name="X-API-Key", auto_error=False, description="Chave de API administrativa via header X-API-Key")


def const_time_compare(val1: str, val2: str) -> bool:
    """
    Compara duas strings em tempo constante usando hmac.compare_digest
    para imunidade completa contra Timing Attacks (OWASP Top 10).
    """
    if not isinstance(val1, str) or not isinstance(val2, str):
        return False
    return hmac.compare_digest(val1.strip(), val2.strip())


async def validar_admin_api_key(
    bearer_creds: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    x_api_key: Optional[str] = Security(api_key_header_scheme),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Api-Key")
) -> str:
    """
    Dependência de segurança para endpoints administrativos e analíticos (FastAPI).
    
    Regras de autenticação:
    1. Se settings.ADMIN_API_KEY não estiver configurada (vazia), permite acesso em modo
       zero-friction (ideal para desenvolvimento local e suítes de teste).
    2. Se settings.ADMIN_API_KEY estiver configurada, exige a chave correta via:
       - Header 'Authorization: Bearer <key>'
       - Header 'X-API-Key: <key>'
       - Header 'X-Admin-Api-Key: <key>'
    3. Rejeita requisições não autenticadas ou com tokens inválidos com HTTP 401 Unauthorized.
    """
    token_esperado = (settings.ADMIN_API_KEY or "").strip()

    # Modo Zero-Friction: desenvolvimento local ou ambientes sem chave configurada
    if not token_esperado:
        return "unprotected-dev-mode"

    # Extrai o token fornecido em qualquer um dos headers suportados
    token_fornecido: Optional[str] = None
    if bearer_creds and bearer_creds.credentials:
        token_fornecido = bearer_creds.credentials.strip()
    elif x_api_key:
        token_fornecido = x_api_key.strip()
    elif x_admin_key:
        token_fornecido = x_admin_key.strip()

    # Caso nenhum token tenha sido fornecido
    if not token_fornecido:
        logger.warning("[SEGURANÇA] 🛑 Acesso bloqueado: chave de autenticação ausente.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso não autorizado: Chave de API ou Token Bearer ausente.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Validação em tempo constante contra timing attacks
    if not const_time_compare(token_fornecido, token_esperado):
        logger.warning("[SEGURANÇA] 🛑 Acesso bloqueado: chave de autenticação incorreta fornecida.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso não autorizado: Chave de API inválida.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    return token_fornecido


from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware defensivo de cabeçalhos de segurança (OWASP Secure Headers).
    Injeta headers recomendados em todas as respostas HTTP da aplicação:
    - X-Content-Type-Options: Impede MIME sniffing
    - X-Frame-Options: Previne ataques de Clickjacking
    - X-XSS-Protection: Habilita bloqueio de XSS em navegadores legado
    - Referrer-Policy: Protege referências entre origens
    - Permissions-Policy: Restringe acesso a recursos sensíveis do cliente
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return response
