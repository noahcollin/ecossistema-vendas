"""
Testes de Integração para os Endpoints de Configurações Operacionais (/settings).
Valida leitura com seed padrão, atualização dinâmica de produtos/preços/cadência/horários,
invalidação de cache no Redis e proteção de segurança da API.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from main import app
from core.config import settings
from core.database import AsyncSessionLocal
from repositories.settings_repository import SettingsRepository, DEFAULT_OPERACAO_SETTINGS


@pytest.fixture(autouse=True)
async def reset_settings_default():
    """Garante que as configurações operacionais iniciem com os defaults em cada teste."""
    from integrations.redis.buffer import redis_client
    from services.settings.settings_service import REDIS_KEY_SETTINGS
    try:
        await redis_client.delete(REDIS_KEY_SETTINGS)
    except Exception:
        pass
    async with AsyncSessionLocal() as db:
        await SettingsRepository.salvar_ou_atualizar(db, DEFAULT_OPERACAO_SETTINGS, chave="geral")
    yield
    try:
        await redis_client.delete(REDIS_KEY_SETTINGS)
    except Exception:
        pass
    async with AsyncSessionLocal() as db:
        await SettingsRepository.salvar_ou_atualizar(db, DEFAULT_OPERACAO_SETTINGS, chave="geral")


@pytest.mark.asyncio
async def test_obter_configuracoes_padrao():
    """Valida que GET /settings/operacao retorna os dados com seed automático."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/settings/operacao")
        assert res.status_code == 200
        dados = res.json()

        assert "produtos" in dados
        assert len(dados["produtos"]) >= 3
        assert "cadencia" in dados
        assert dados["cadencia"]["max_tentativas"] == 3
        assert "horario_comercial" in dados
        assert dados["horario_comercial"]["inicio_hora"] == 8
        assert dados["horario_comercial"]["fim_hora"] == 18
        assert dados["debounce_segundos"] == 4.5


@pytest.mark.asyncio
async def test_atualizar_configuracoes_operacionais():
    """Valida que PUT /settings/operacao atualiza produtos, preços e cadência em tempo real."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Obtém as configurações atuais
        res_get = await client.get("/settings/operacao")
        assert res_get.status_code == 200
        atuais = res_get.json()

        # 2. Modifica o preço do primeiro produto e a quantidade de tentativas de cadência
        produtos_modificados = atuais["produtos"]
        produtos_modificados[0]["preco_base_mensal"] = 4900.0
        produtos_modificados.append({
            "id": "novo_produto_teste",
            "nome": "Consultoria de IA Customizada",
            "descricao": "Desenvolvimento sob medida de integrações",
            "preco_base_mensal": 8000.0,
            "taxa_setup": 3000.0,
            "ativo": True
        })

        payload_update = {
            "produtos": produtos_modificados,
            "cadencia": {
                "max_tentativas": 5,
                "intervalo_horas": 12,
                "apenas_dias_uteis": False,
                "respeitar_horario_comercial": True
            },
            "horario_comercial": {
                "inicio_hora": 7,
                "fim_hora": 20,
                "dias_semana": [0, 1, 2, 3, 4, 5],
                "fuso_horario": "America/Sao_Paulo"
            },
            "debounce_segundos": 5.0
        }

        # 3. Executa o PUT
        res_put = await client.put("/settings/operacao", json=payload_update)
        assert res_put.status_code == 200
        dados_atualizados = res_put.json()

        assert dados_atualizados["cadencia"]["max_tentativas"] == 5
        assert dados_atualizados["cadencia"]["intervalo_horas"] == 12
        assert dados_atualizados["horario_comercial"]["fim_hora"] == 20
        assert dados_atualizados["debounce_segundos"] == 5.0
        assert len(dados_atualizados["produtos"]) == len(produtos_modificados)
        
        # 4. Confirma que o próximo GET retorna imediatamente os dados novos (persiste no banco e cache)
        res_get_depois = await client.get("/settings/operacao")
        assert res_get_depois.status_code == 200
        dados_depois = res_get_depois.json()
        assert dados_depois["cadencia"]["max_tentativas"] == 5
        assert dados_depois["produtos"][0]["preco_base_mensal"] == 4900.0
        assert any(p["id"] == "novo_produto_teste" for p in dados_depois["produtos"])


@pytest.mark.asyncio
async def test_seguranca_settings_com_api_key(monkeypatch):
    """Garante que endpoints /settings/operacao exigem autenticação quando ADMIN_API_KEY estiver configurada."""
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "chave_admin_ultra_secreta_999")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Sem chave -> 401
        res_anon = await client.get("/settings/operacao")
        assert res_anon.status_code == 401

        # Chave errada -> 401
        res_errada = await client.get(
            "/settings/operacao",
            headers={"X-API-Key": "chave_incorreta"}
        )
        assert res_errada.status_code == 401

        # Chave correta via X-API-Key -> 200 OK
        res_correta = await client.get(
            "/settings/operacao",
            headers={"X-API-Key": "chave_admin_ultra_secreta_999"}
        )
        assert res_correta.status_code == 200
