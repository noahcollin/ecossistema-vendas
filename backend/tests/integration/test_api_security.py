"""
Suíte de Testes de Integração: Segurança, Autenticação e Headers OWASP
========================================================================
Valida a camada de segurança da API do ecossistema:
1. Injeção obrigatória de cabeçalhos OWASP defensivos em todas as respostas HTTP.
2. Acessibilidade pública contínua de rotas vitais (/ e /health) para orquestradores.
3. Bloqueio estrito (HTTP 401) em rotas protegidas (/leads e /analytics) sem autenticação.
4. Rejeição de tokens e chaves de API incorretas (imunidade a timing attacks).
5. Autorização bem-sucedida via header padrão 'Authorization: Bearer <token>'.
6. Autorização bem-sucedida via headers de API Key ('X-API-Key' e 'X-Admin-Api-Key').
7. Modo zero-friction quando ADMIN_API_KEY está vazia (preservação do fluxo de desenvolvimento).
"""

import os
import sys
import pytest
from httpx import AsyncClient, ASGITransport

# Ajusta path para importar módulos do backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from main import app
from core.config import settings

TEST_MASTER_KEY = "segredo-mestre-super-seguro-api-key-2026"


@pytest.fixture(autouse=True)
def restore_settings():
    """Garante que as configurações originais sejam preservadas após cada teste."""
    original_key = settings.ADMIN_API_KEY
    yield
    settings.ADMIN_API_KEY = original_key


@pytest.mark.asyncio
async def test_owasp_security_headers_present_on_all_responses():
    """Valida a injeção dos cabeçalhos OWASP defensivos no middleware."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for rota in ["/", "/health"]:
            res = await client.get(rota)
            assert res.status_code == 200
            headers = res.headers
            assert headers.get("x-content-type-options") == "nosniff"
            assert headers.get("x-frame-options") == "DENY"
            assert headers.get("x-xss-protection") == "1; mode=block"
            assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
            assert "geolocation=()" in headers.get("permissions-policy", "")


@pytest.mark.asyncio
async def test_public_endpoints_accessible_without_auth():
    """Garante que / e /health permaneçam públicos mesmo com ADMIN_API_KEY configurada."""
    settings.ADMIN_API_KEY = TEST_MASTER_KEY
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_root = await client.get("/")
        assert res_root.status_code == 200

        res_health = await client.get("/health")
        assert res_health.status_code == 200


@pytest.mark.asyncio
async def test_protected_endpoints_reject_unauthenticated_requests():
    """Garante que /leads e /analytics rejeitem requisições sem credenciais com HTTP 401."""
    settings.ADMIN_API_KEY = TEST_MASTER_KEY
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Rotas de Leads
        res_leads = await client.get("/leads/")
        assert res_leads.status_code == 401
        assert "WWW-Authenticate" in res_leads.headers

        res_transbordo = await client.get("/leads/transbordo/pendentes")
        assert res_transbordo.status_code == 401

        # Rotas de Analytics
        res_overview = await client.get("/analytics/overview")
        assert res_overview.status_code == 401

        res_financeiro = await client.get("/analytics/financeiro")
        assert res_financeiro.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoints_reject_invalid_token():
    """Garante que tokens ou chaves inválidas sejam rejeitadas com HTTP 401."""
    settings.ADMIN_API_KEY = TEST_MASTER_KEY
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Bearer inválido
        res_bad_bearer = await client.get(
            "/leads/",
            headers={"Authorization": "Bearer token-falso-e-malicioso"}
        )
        assert res_bad_bearer.status_code == 401

        # X-API-Key inválida
        res_bad_key = await client.get(
            "/analytics/overview",
            headers={"X-API-Key": "chave-falsa-123"}
        )
        assert res_bad_key.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoints_accept_valid_bearer_token():
    """Garante que requisições com Authorization: Bearer <valid_key> sejam autorizadas (HTTP 200)."""
    settings.ADMIN_API_KEY = TEST_MASTER_KEY
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        auth_header = {"Authorization": f"Bearer {TEST_MASTER_KEY}"}

        res_leads = await client.get("/leads/", headers=auth_header)
        assert res_leads.status_code == 200

        res_analytics = await client.get("/analytics/overview", headers=auth_header)
        assert res_analytics.status_code == 200


@pytest.mark.asyncio
async def test_protected_endpoints_accept_valid_api_key_headers():
    """Garante autorização via headers X-API-Key e X-Admin-Api-Key."""
    settings.ADMIN_API_KEY = TEST_MASTER_KEY
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Header X-API-Key
        res_x_key = await client.get("/leads/", headers={"X-API-Key": TEST_MASTER_KEY})
        assert res_x_key.status_code == 200

        # Header alternativo X-Admin-Api-Key
        res_admin_key = await client.get(
            "/analytics/financeiro",
            headers={"X-Admin-Api-Key": TEST_MASTER_KEY}
        )
        assert res_admin_key.status_code == 200


@pytest.mark.asyncio
async def test_unprotected_dev_mode_when_admin_key_is_empty():
    """Valida o modo zero-friction: se ADMIN_API_KEY for vazia, rotas operam abertas para testes locais."""
    settings.ADMIN_API_KEY = ""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res_leads = await client.get("/leads/")
        assert res_leads.status_code == 200

        res_analytics = await client.get("/analytics/overview")
        assert res_analytics.status_code == 200
