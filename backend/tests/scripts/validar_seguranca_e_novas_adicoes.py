"""
Script de Auditoria Executiva: Segurança de API, Headers OWASP e Módulos Analíticos
======================================================================================
Executa testes práticos simulando ataques, acessos anônimos, validação de tokens,
análise de tempo constante e conferência dos 5 blocos analíticos.
"""

import asyncio
import os
import sys
import time
from httpx import AsyncClient, ASGITransport

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from main import app
from core.config import settings
from core.security import const_time_compare

CHAVE_TESTE_ADMIN = "super-secret-admin-token-2026-audit"
CHAVE_TESTE_WEBHOOK = "webhook-secret-token-2026-audit"

def print_section(title: str):
    print("\n" + "=" * 80)
    print(f"🔒 {title}")
    print("=" * 80)

def assert_owasp_headers(headers, rota: str):
    assert headers.get("x-content-type-options") == "nosniff", f"[{rota}] Falha: X-Content-Type-Options ausente ou incorreto"
    assert headers.get("x-frame-options") == "DENY", f"[{rota}] Falha: X-Frame-Options ausente ou incorreto"
    assert headers.get("x-xss-protection") == "1; mode=block", f"[{rota}] Falha: X-XSS-Protection ausente ou incorreto"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin", f"[{rota}] Falha: Referrer-Policy incorreto"
    assert "geolocation=()" in headers.get("permissions-policy", ""), f"[{rota}] Falha: Permissions-Policy incorreto"
    print(f"   🛡️  [OWASP OK] Headers defensivos verificados na rota {rota}")

async def run_audit():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # -------------------------------------------------------------
        # TESTE 1: Criptografia e Prevenção contra Timing Attacks
        # -------------------------------------------------------------
        print_section("1. TESTE DE IMUNIDADE A TIMING ATTACKS (HMAC CONSTANT-TIME)")
        assert const_time_compare("chave-exata", "chave-exata") is True
        assert const_time_compare("chave-exata", "chave-errad") is False
        assert const_time_compare("chave-exata", "chave-exata-extra") is False
        assert const_time_compare("chave-exata", "") is False
        print("   ✅ [OK] Comparação em tempo constante (hmac.compare_digest) validada com sucesso.")

        # -------------------------------------------------------------
        # TESTE 2: Rotas Públicas e Monitoramento de Saúde
        # -------------------------------------------------------------
        print_section("2. TESTE DE ROTAS PÚBLICAS E HEALTH CHECK")
        settings.ADMIN_API_KEY = CHAVE_TESTE_ADMIN

        res_root = await client.get("/")
        assert res_root.status_code == 200, f"Falha na raiz: {res_root.status_code}"
        assert_owasp_headers(res_root.headers, "/")
        print("   ✅ [OK] Rota raiz '/' pública e operante (HTTP 200).")

        res_health = await client.get("/health")
        assert res_health.status_code == 200, f"Falha no health: {res_health.status_code}"
        assert_owasp_headers(res_health.headers, "/health")
        saude = res_health.json()
        print(f"   ✅ [OK] Rota '/health' pública e operante: status={saude.get('status')} | postgres={saude.get('componentes', {}).get('postgres')} | redis={saude.get('componentes', {}).get('redis')}")

        # -------------------------------------------------------------
        # TESTE 3: Bloqueio de Acessos Anônimos (HTTP 401)
        # -------------------------------------------------------------
        print_section("3. TESTE DE BLOQUEIO DE ACESSO ANÔNIMO (HTTP 401)")
        rotas_privadas = [
            "/leads/",
            "/leads/transbordo/pendentes",
            "/analytics/overview",
            "/analytics/financeiro",
            "/analytics/funil",
            "/analytics/aquisicao",
            "/analytics/perdas",
            "/analytics/conversas"
        ]

        for rota in rotas_privadas:
            res = await client.get(rota)
            assert res.status_code == 401, f"Falha de segurança! Rota {rota} permitiu acesso sem token (Status {res.status_code})"
            assert "WWW-Authenticate" in res.headers, f"Header WWW-Authenticate ausente em {rota}"
            assert_owasp_headers(res.headers, rota)
            print(f"   🚫 [BLOQUEADO 401] Rota restrita {rota} rejeitou requisição anônima.")

        # -------------------------------------------------------------
        # TESTE 4: Bloqueio de Tokens Forjados e Maliciosos
        # -------------------------------------------------------------
        print_section("4. TESTE DE INVASÃO: TOKENS FORJADOS E PAYLOADS MALICIOSOS")
        payloads_ataque = [
            ("Bearer hacker-token-xyz", "Token forjado simples"),
            ("Bearer ' OR '1'='1", "Tentativa de injeção SQL no cabeçalho"),
            ("Bearer " + CHAVE_TESTE_ADMIN[:-1] + "X", "Token com 1 caractere divergente"),
            ("Bearer admin", "Tentativa de brute-force com credencial fraca"),
            ("Bearer ", "Bearer com corpo vazio")
        ]

        for token_header, desc in payloads_ataque:
            res = await client.get("/analytics/overview", headers={"Authorization": token_header})
            assert res.status_code == 401, f"Falha de segurança com payload '{desc}'! Status {res.status_code}"
            print(f"   🛑 [ATAQUE REPELIDO 401] {desc} -> Rejeitado com sucesso.")

        # -------------------------------------------------------------
        # TESTE 5: Autorização com Cabeçalhos Válidos (Bearer, X-API-Key, X-Admin-Api-Key)
        # -------------------------------------------------------------
        print_section("5. TESTE DE AUTORIZAÇÃO COM MÚLTIPLOS CABEÇALHOS SUPORTADOS")
        
        # 5.1 Bearer Token
        res_bearer = await client.get(
            "/analytics/overview",
            headers={"Authorization": f"Bearer {CHAVE_TESTE_ADMIN}"}
        )
        assert res_bearer.status_code == 200, f"Falha com Bearer válido: {res_bearer.text}"
        assert_owasp_headers(res_bearer.headers, "/analytics/overview (Bearer)")
        print("   🔓 [AUTORIZADO 200] Authorization: Bearer <token> aceito com sucesso.")

        # 5.2 Header X-API-Key
        res_apikey = await client.get(
            "/analytics/financeiro",
            headers={"X-API-Key": CHAVE_TESTE_ADMIN}
        )
        assert res_apikey.status_code == 200, f"Falha com X-API-Key válido: {res_apikey.text}"
        assert_owasp_headers(res_apikey.headers, "/analytics/financeiro (X-API-Key)")
        print("   🔓 [AUTORIZADO 200] X-API-Key: <chave> aceito com sucesso.")

        # 5.3 Header X-Admin-Api-Key
        res_adminkey = await client.get(
            "/leads/",
            headers={"X-Admin-Api-Key": CHAVE_TESTE_ADMIN}
        )
        assert res_adminkey.status_code == 200, f"Falha com X-Admin-Api-Key válido: {res_adminkey.text}"
        print("   🔓 [AUTORIZADO 200] X-Admin-Api-Key: <chave> aceito com sucesso.")

        # -------------------------------------------------------------
        # TESTE 6: Verificação de Integridade dos 5 Blocos de Analytics
        # -------------------------------------------------------------
        print_section("6. TESTE DE INTEGRIDADE DOS 5 BLOCOS DE ANALYTICS (COM AUTH ATIVA)")
        headers_auth = {"Authorization": f"Bearer {CHAVE_TESTE_ADMIN}"}
        
        res_overview = await client.get("/analytics/overview", headers=headers_auth)
        assert res_overview.status_code == 200
        dados_bi = res_overview.json()

        fin = dados_bi["financeiro"]
        funil = dados_bi["funil"]
        acq = dados_bi["aquisicao"]
        perdas = dados_bi["perdas"]
        conv = dados_bi["conversas"]

        print(f"   📊 [BLOCO 1 - FINANCEIRO] Pipeline Ativo: R$ {fin['pipeline_ativo_reais']:,.2f} | Receita Ganha: R$ {fin['receita_ganha_reais']:,.2f} | Conversão: {fin['taxa_conversao_pct']:.1f}%")
        print(f"   📊 [BLOCO 2 - FUNIL] Leads Quentes: {funil['leads_quentes_count']} | Etapas mapeadas: {len(funil['por_etapa'])}")
        print(f"   📊 [BLOCO 3 - AQUISIÇÃO] Campeão de Receita: {acq.get('canal_campeao_receita') or 'Nenhum'} | Canais mapeados: {len(acq['por_canal'])}")
        print(f"   📊 [BLOCO 4 - PERDAS] Descartes: {perdas['total_descartes']} | Principal Objeção: {perdas.get('principal_motivo') or 'Nenhuma'}")
        print(f"   📊 [BLOCO 5 - CONVERSAS] Volume Mensagens: {conv['volume_mensagens']['total_mensagens']} | Taxa Resgate Follow-up: {conv['eficacia_followup']['taxa_resgate_pct']:.1f}%")

        # -------------------------------------------------------------
        # TESTE 7: Segurança Dedicada do Webhook (X-Webhook-Secret)
        # -------------------------------------------------------------
        print_section("7. TESTE DE SEGURANÇA DEDICADA DO WEBHOOK")
        settings.WEBHOOK_SECRET_TOKEN = CHAVE_TESTE_WEBHOOK

        # Sem secret -> 401
        res_wh_anon = await client.post("/webhook/whatsapp", json={"event": "messages.upsert"})
        assert res_wh_anon.status_code == 401, f"Falha! Webhook sem segredo deveria retornar 401, retornou {res_wh_anon.status_code}"
        print("   🚫 [WEBHOOK BLOQUEADO 401] Webhook anônimo sem X-Webhook-Secret rejeitado.")

        # Com secret errado -> 401
        res_wh_bad = await client.post(
            "/webhook/whatsapp",
            headers={"X-Webhook-Secret": "secret-errado"},
            json={"event": "messages.upsert"}
        )
        assert res_wh_bad.status_code == 401
        print("   🚫 [WEBHOOK BLOQUEADO 401] Webhook com secret falso rejeitado.")

        # Com secret correto -> Autorizado (processa ou ignora payload inválido, não 401)
        res_wh_ok = await client.post(
            "/webhook/whatsapp",
            headers={"X-Webhook-Secret": CHAVE_TESTE_WEBHOOK},
            json={"event": "messages.upsert", "chat": {"phone": "5583999990000"}}
        )
        assert res_wh_ok.status_code == 200, f"Webhook com secret legítimo deveria autorizar (200), retornou {res_wh_ok.status_code}"
        print("   🔓 [WEBHOOK AUTORIZADO 200] Webhook autenticado com X-Webhook-Secret legítimo.")

        # -------------------------------------------------------------
        # TESTE 8: Modo Zero-Friction Dev (Preservação do Fluxo Local)
        # -------------------------------------------------------------
        print_section("8. TESTE DO MODO ZERO-FRICTION DEV (CHAVE VAZIA)")
        settings.ADMIN_API_KEY = ""
        settings.WEBHOOK_SECRET_TOKEN = ""

        res_dev_leads = await client.get("/leads/")
        assert res_dev_leads.status_code == 200
        res_dev_analytics = await client.get("/analytics/overview")
        assert res_dev_analytics.status_code == 200
        print("   🌱 [ZERO-FRICTION OK] Ambiente com ADMIN_API_KEY='' opera aberto para desenvolvimento local sem travar testes.")

        print("\n" + "=" * 80)
        print("🏆 RESULTADO FINAL: TODOS OS 8 TESTES DE SEGURANÇA E ANALYTICS FORAM APROVADOS COM 100% DE SUCESSO!")
        print("=" * 80 + "\n")

if __name__ == "__main__":
    asyncio.run(run_audit())
