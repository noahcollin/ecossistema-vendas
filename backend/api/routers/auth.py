"""
Router de Autenticação Corporativa (Locaweb IMAP + JWT).
Permite login seguro da equipe Inteligentte usando credenciais do webmail corporativo.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from core.security import validar_admin_api_key
from services.auth_locaweb_service import LocawebAuthService


router = APIRouter(prefix="/auth", tags=["Autenticação Corporativa"])


class LoginRequest(BaseModel):
    email: str = Field(..., description="E-mail corporativo @inteligentte.com.br")
    senha: str = Field(..., description="Senha do Webmail Locaweb")


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    email: str
    expires_in_hours: int


class UserProfileResponse(BaseModel):
    email: str
    authenticated: bool
    role: str = "operator"


@router.post("/login", response_model=LoginResponse)
async def login_corporativo(body: LoginRequest):
    """
    Autentica o colaborador usando as credenciais do seu e-mail corporativo da Locaweb.
    Retorna um Token JWT de sessão de 72 horas para navegação no Dashboard.
    """
    sucesso = await LocawebAuthService.autenticar_email_locaweb(body.email, body.senha)
    if not sucesso:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas. Verifique seu e-mail corporativo e senha da Locaweb."
        )

    token = LocawebAuthService.gerar_token_jwt(body.email)
    return LoginResponse(
        access_token=token,
        email=body.email.lower().strip(),
        expires_in_hours=72
    )


@router.get("/me", response_model=UserProfileResponse)
async def obter_sessao_atual(operador: str = Depends(validar_admin_api_key)):
    """Verifica se a sessão corporativa ou chave de API atual é válida."""
    email = operador.replace("operator:", "") if operador.startswith("operator:") else "admin"
    return UserProfileResponse(
        email=email,
        authenticated=True
    )
