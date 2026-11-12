import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from main import app

@pytest.mark.asyncio
async def test_login_dominio_invalido():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post("/auth/login", json={
            "email": "hacker@gmail.com",
            "senha": "qualquersenhainvalida"
        })
        assert res.status_code == 401
        assert "Credenciais inválidas" in res.json()["detail"]

@pytest.mark.asyncio
async def test_login_sucesso_com_mock_locaweb():
    with patch("services.auth_locaweb_service.LocawebAuthService._verificar_credenciais_imap_sync", return_value=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            res = await client.post("/auth/login", json={
                "email": "equipe@inteligentte.com.br",
                "senha": "senha-correta"
            })
            assert res.status_code == 200
            data = res.json()
            assert "access_token" in data
            assert data["email"] == "equipe@inteligentte.com.br"
            token = data["access_token"]

            # Testar rota protegida /auth/me usando o JWT gerado
            res_me = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
            assert res_me.status_code == 200
            assert res_me.json()["email"] == "equipe@inteligentte.com.br"
