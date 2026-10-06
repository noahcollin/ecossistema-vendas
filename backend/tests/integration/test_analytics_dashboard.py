"""
Suíte de Testes de Integração: Dashboard de Analytics e Inteligência Comercial
================================================================================
Valida os 6 endpoints de Business Intelligence comercial:
1. GET /analytics/overview (Painel Executivo Consolidado)
2. GET /analytics/financeiro (Pipeline Ativo, Receita Ganha e Conversão)
3. GET /analytics/funil (Distribuição por Etapa e Leads Quentes)
4. GET /analytics/aquisicao (Performance de Canais e Inbound vs Outbound)
5. GET /analytics/perdas (Ranking de Motivos de Descarte e Objeções)
6. GET /analytics/conversas (Volume WhatsApp e Eficácia da Cadência)

Garante conformidade com Pydantic v2 e consistência matemática contra o banco real.
"""

import os
import sys
import uuid
import pytest
from httpx import AsyncClient, ASGITransport

# Ajusta path para importar módulos do backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from main import app
from core.database import AsyncSessionLocal
import models
import schemas
from repositories.lead_repository import LeadRepository


@pytest.mark.asyncio
async def test_analytics_endpoints_status_and_contracts():
    """Valida se todos os 6 endpoints de analytics retornam HTTP 200 e schemas válidos."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Overview Consolidado
        res_overview = await client.get("/analytics/overview")
        assert res_overview.status_code == 200, f"Overview falhou: {res_overview.text}"
        data_overview = res_overview.json()
        assert "gerado_em" in data_overview
        assert "total_leads_cadastrados" in data_overview
        assert "financeiro" in data_overview
        assert "funil" in data_overview
        assert "aquisicao" in data_overview
        assert "perdas" in data_overview
        assert "conversas" in data_overview

        # 2. Financeiro
        res_fin = await client.get("/analytics/financeiro")
        assert res_fin.status_code == 200
        data_fin = res_fin.json()
        assert data_fin["pipeline_ativo_reais"] >= 0.0
        assert data_fin["receita_ganha_reais"] >= 0.0
        assert 0.0 <= data_fin["taxa_conversao_pct"] <= 100.0

        # 3. Funil
        res_funil = await client.get("/analytics/funil")
        assert res_funil.status_code == 200
        data_funil = res_funil.json()
        assert "por_etapa" in data_funil
        assert "por_temperatura" in data_funil
        assert isinstance(data_funil["leads_quentes_count"], int)

        # 4. Aquisição
        res_aquisicao = await client.get("/analytics/aquisicao")
        assert res_aquisicao.status_code == 200
        data_aquisicao = res_aquisicao.json()
        assert "por_canal" in data_aquisicao
        assert "por_tipo_entrada" in data_aquisicao

        # 5. Perdas
        res_perdas = await client.get("/analytics/perdas?limite=5")
        assert res_perdas.status_code == 200
        data_perdas = res_perdas.json()
        assert "motivos_ranking" in data_perdas
        assert len(data_perdas["motivos_ranking"]) <= 5

        # 6. Conversas & Follow-up
        res_conversas = await client.get("/analytics/conversas")
        assert res_conversas.status_code == 200
        data_conversas = res_conversas.json()
        assert "volume_mensagens" in data_conversas
        assert "eficacia_followup" in data_conversas


@pytest.mark.asyncio
async def test_analytics_dynamic_data_aggregation_and_isolation():
    """
    Testa a reatividade do Analytics inserindo leads controlados:
    - 1 Lead GANHO de R$ 50.000,00 via META_ADS
    - 1 Lead PERDIDO de R$ 20.000,00 por 'Preço Alto'
    Verifica se os números refletem nos cálculos e realiza cleanup ao final.
    """
    tel_ganho = f"+558399999{uuid.uuid4().int % 10000:04d}"
    tel_perdido = f"+558399999{uuid.uuid4().int % 10000:04d}"

    async with AsyncSessionLocal() as db:
        # Cria lead ganho
        lead_ganho = models.Lead(
            telefone=tel_ganho,
            nome="Empresa Teste Ganho",
            etapa_funil=models.EtapaFunil.FECHAMENTO,
            desfecho=models.DesfechoLead.GANHO,
            temperatura=models.TemperaturaLead.QUENTE,
            valor_estimado=50000.0,
            origem_canal="META_ADS",
            tipo_entrada=models.TipoEntradaLead.INBOUND,
            controle=models.ControleAtendimento.HUMANO_ASSUMIU
        )
        # Cria lead perdido
        lead_perdido = models.Lead(
            telefone=tel_perdido,
            nome="Empresa Teste Perdido",
            etapa_funil=models.EtapaFunil.QUALIFICACAO,
            desfecho=models.DesfechoLead.PERDIDO,
            temperatura=models.TemperaturaLead.FRIO,
            valor_estimado=20000.0,
            motivo_perda="Preço Alto / Sem Budget",
            origem_canal="SITE_LANDING_PAGE",
            tipo_entrada=models.TipoEntradaLead.INBOUND,
            controle=models.ControleAtendimento.PILOTO_IA
        )
        db.add(lead_ganho)
        db.add(lead_perdido)
        await db.commit()
        await db.refresh(lead_ganho)
        await db.refresh(lead_perdido)

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Verifica no endpoint de financeiro
            res_fin = await client.get("/analytics/financeiro")
            assert res_fin.status_code == 200
            data_fin = res_fin.json()
            assert data_fin["receita_ganha_reais"] >= 50000.0
            assert data_fin["valor_perdido_reais"] >= 20000.0
            assert data_fin["total_leads_ganhos"] >= 1
            assert data_fin["total_leads_perdidos"] >= 1

            # 2. Verifica no endpoint de perdas
            res_perdas = await client.get("/analytics/perdas")
            assert res_perdas.status_code == 200
            data_perdas = res_perdas.json()
            assert data_perdas["total_descartes"] >= 1
            motivos = [m["motivo"] for m in data_perdas["motivos_ranking"]]
            assert "Preço Alto / Sem Budget" in motivos

            # 3. Verifica no endpoint de aquisição
            res_acq = await client.get("/analytics/aquisicao")
            assert res_acq.status_code == 200
            data_acq = res_acq.json()
            canais = [c["origem_canal"] for c in data_acq["por_canal"]]
            assert "META_ADS" in canais

    finally:
        # Limpeza (Cleanup) para manter o banco limpo e testes idempotentes
        async with AsyncSessionLocal() as db:
            for tel in [tel_ganho, tel_perdido]:
                lead_rem = await LeadRepository.get_by_phone(db, tel)
                if lead_rem:
                    await LeadRepository.delete_interactions_by_lead_id(db, lead_rem.id)
                    await LeadRepository.delete_lead(db, lead_rem)


@pytest.mark.asyncio
async def test_analytics_conversas_and_followup_metrics():
    """
    Testa a agregação de interações no WhatsApp e eficácia dos follow-ups agendados.
    """
    from datetime import datetime, timezone
    tel_conversa = f"+558398888{uuid.uuid4().int % 10000:04d}"

    async with AsyncSessionLocal() as db:
        lead = models.Lead(
            telefone=tel_conversa,
            nome="Lead Teste Mensagens",
            etapa_funil=models.EtapaFunil.QUALIFICACAO,
            desfecho=models.DesfechoLead.EM_ANDAMENTO,
            temperatura=models.TemperaturaLead.MORNO,
            controle=models.ControleAtendimento.PILOTO_IA
        )
        db.add(lead)
        await db.commit()
        await db.refresh(lead)

        # Adiciona interações
        msg_cliente = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.CLIENTE,
            texto="Olá, gostaria de saber os planos."
        )
        msg_ia = models.Interacao(
            lead_id=lead.id,
            origem=models.InteracaoOrigem.IA,
            texto="Olá! Nossos planos começam em R$ 1.500/mês."
        )
        # Adiciona follow-up disparado
        agendamento = models.FollowupAgendado(
            lead_id=lead.id,
            etapa_funil=models.EtapaFunil.QUALIFICACAO,
            tentativa=1,
            agendado_para=datetime.now(timezone.utc).replace(tzinfo=None),
            status=models.StatusFollowup.DISPARADO,
            mensagem_disparada="Tudo bem? Ficou alguma dúvida sobre os planos?"
        )
        db.add(msg_cliente)
        db.add(msg_ia)
        db.add(agendamento)
        await db.commit()

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/analytics/conversas")
            assert res.status_code == 200
            data = res.json()
            vol = data["volume_mensagens"]
            fol = data["eficacia_followup"]

            assert vol["total_mensagens"] >= 2
            assert vol["mensagens_clientes"] >= 1
            assert vol["mensagens_operacao"] >= 1
            assert fol["total_disparados"] >= 1
    finally:
        async with AsyncSessionLocal() as db:
            lead_rem = await LeadRepository.get_by_phone(db, tel_conversa)
            if lead_rem:
                await LeadRepository.delete_interactions_by_lead_id(db, lead_rem.id)
                await LeadRepository.delete_lead(db, lead_rem)


@pytest.mark.asyncio
async def test_analytics_perdas_query_validation():
    """Valida os parâmetros de query e paginação do ranking de perdas."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Limite válido = 1
        res_ok = await client.get("/analytics/perdas?limite=1")
        assert res_ok.status_code == 200
        data = res_ok.json()
        assert len(data["motivos_ranking"]) <= 1

        # Limite inválido = 0 (validação Pydantic/FastAPI ge=1 deve retornar 422)
        res_invalid = await client.get("/analytics/perdas?limite=0")
        assert res_invalid.status_code == 422

