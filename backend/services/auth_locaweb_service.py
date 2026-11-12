"""
Serviço de Autenticação Corporativa Locaweb e Emissão de Tokens JWT.
Autentica e-mails corporativos (@inteligentte.com.br) via protocolo IMAP SSL nativo da Locaweb.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import imaplib
import ssl
from typing import Optional
import jwt

from core.config import settings
from core.logger import logger


class LocawebAuthService:
    """
    Realiza a autenticação de contas de e-mail corporativas
    diretamente no servidor seguro da Locaweb via IMAP SSL (porta 993).
    """

    @classmethod
    def _verificar_credenciais_imap_sync(cls, email: str, senha: str) -> bool:
        """Executa a conexão e tentativa de login IMAP SSL síncrona."""
        context = ssl.create_default_context()
        try:
            with imaplib.IMAP4_SSL(
                host=settings.LOCAWEB_IMAP_SERVER,
                port=settings.LOCAWEB_IMAP_PORT,
                ssl_context=context,
                timeout=10.0
            ) as imap:
                status, _ = imap.login(email, senha)
                return status == "OK"
        except imaplib.IMAP4.error as err:
            logger.warning(f"[AUTH LOCAWEB] 🔒 Falha de autenticação IMAP para {email}: {err}")
            return False
        except Exception as err:
            logger.error(f"[AUTH LOCAWEB] ❌ Erro de comunicação com servidor IMAP da Locaweb: {err}", exc_info=True)
            return False

    @classmethod
    async def autenticar_email_locaweb(cls, email: str, senha: str) -> bool:
        """
        Valida se o e-mail pertence ao domínio permitido (@inteligentte.com.br)
        e se as credenciais são válidas no servidor da Locaweb.
        """
        email_limpo = (email or "").strip().lower()
        senha_limpa = (senha or "").strip()

        if not email_limpo or not senha_limpa:
            return False

        # Validação estrita do domínio corporativo
        dominio_esperado = f"@{settings.ALLOWED_EMAIL_DOMAIN.lower()}"
        if not email_limpo.endswith(dominio_esperado):
            logger.warning(
                f"[AUTH LOCAWEB] 🚫 Tentativa de login bloqueada: {email_limpo} "
                f"não pertence ao domínio permitido {dominio_esperado}"
            )
            return False

        # Executa a verificação IMAP em threadpool assíncrono para não bloquear o Event Loop do FastAPI
        return await asyncio.to_thread(cls._verificar_credenciais_imap_sync, email_limpo, senha_limpa)

    @classmethod
    def gerar_token_jwt(cls, email: str) -> str:
        """Gera um JWT de sessão corporativa com validade configurável."""
        agora = datetime.now(timezone.utc)
        expiracao = agora + timedelta(hours=settings.JWT_EXPIRATION_HOURS)

        payload = {
            "sub": email.strip().lower(),
            "domain": settings.ALLOWED_EMAIL_DOMAIN,
            "iat": agora,
            "exp": expiracao,
            "role": "operator"
        }

        return jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )

    @classmethod
    def decodificar_token_jwt(cls, token: str) -> Optional[dict]:
        """Valida e decodifica o token JWT de sessão. Retorna None se inválido ou expirado."""
        try:
            return jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
