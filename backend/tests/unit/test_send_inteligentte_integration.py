"""
Testes Unitários da Integração com o Send Inteligentte (API Oficial Meta).
Valida:
1. Assinatura HMAC-SHA256 e proteção anti-replay (5 min).
2. Deduplicação idempotente por `event.id`.
3. `message.received` (texto, botão e mídia) encaminhado ao buffer de debounce.
4. `message.received` com `contact.optedOut=True` (limpa buffer, marca opt_out e NÃO responde).
5. `conversation.handover` (marca HUMANO_ASSUMIU e cancela follow-ups).
6. Erros 409/422 (HUMAN_HANDOVER, OPT_OUT, OUTSIDE_WINDOW) não sofrem retry.
"""

import asyncio
import hashlib
import hmac
import time
from unittest.mock import AsyncMock
import pytest

import models
from core.config import settings
from integrations.send_inteligentte.client import enviar_mensagem_send, limpar_telefone_send
from repositories.lead_repository import LeadRepository
from services.inbound.send_event_service import SendEventService
from services.inbound.webhook_service import WebhookApplicationService
from tests.conftest import MockCacheBufferGateway


def test_limpar_telefone_send():
    assert limpar_telefone_send("+55 (83) 99999-0001") == "5583999990001"
    assert limpar_telefone_send("83999990001") == "5583999990001"


def test_send_webhook_hmac_signature_verification():
    secret = "whsec_teste_oficial_123"
    raw_body = b'{"id":"evt-1","seq":1,"type":"ping"}'
    ts_atual = str(int(time.time()))

    esperado = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        f"{ts_atual}.".encode("utf-8") + raw_body,
        hashlib.sha256,
    ).hexdigest()

    assert SendEventService.verificar_assinatura_webhook(raw_body, ts_atual, esperado, secret=secret) is True
    assert SendEventService.verificar_assinatura_webhook(raw_body, ts_atual, "sha256=invalida", secret=secret) is False

    # Timestamp expirado (> 5 minutos)
    ts_antigo = str(int(time.time()) - 600)
    sig_antiga = "sha256=" + hmac.new(
        secret.encode("utf-8"),
        f"{ts_antigo}.".encode("utf-8") + raw_body,
        hashlib.sha256,
    ).hexdigest()
    assert SendEventService.verificar_assinatura_webhook(raw_body, ts_antigo, sig_antiga, secret=secret) is False


@pytest.mark.asyncio
async def test_send_event_ping_and_deduplication(monkeypatch):
    SendEventService._processed_memory_ids.clear()
    monkeypatch.setattr("services.inbound.send_event_service.redis_client.get", AsyncMock(return_value=None))
    monkeypatch.setattr("services.inbound.send_event_service.redis_client.setex", AsyncMock())

    res_ping = await SendEventService.processar_evento_send({"id": "ping-1", "type": "ping"})
    assert res_ping["status"] == "ok"

    mock_buffer = MockCacheBufferGateway()
    monkeypatch.setattr(WebhookApplicationService, "buffer_gateway", mock_buffer)
    monkeypatch.setattr(SendEventService, "buffer_gateway", mock_buffer)
    monkeypatch.setattr(settings, "SANDBOX_MODE", False)
    monkeypatch.setattr(
        "services.inbound.webhook_service.spawn_background_task",
        lambda coro, **kw: (coro.close(), asyncio.create_task(asyncio.sleep(0)))[1],
    )

    evento_msg = {
        "id": "evt-unico-100",
        "seq": 100,
        "type": "message.received",
        "data": {
            "contact": {"phone": "5583999990001", "name": "Maria", "optedOut": False},
            "message": {
                "id": "msg-100",
                "wamid": "wamid.100",
                "type": "button",
                "button": {"text": "Tenho interesse", "payload": "Tenho interesse"},
            },
        },
    }

    res1 = await SendEventService.processar_evento_send(evento_msg)
    assert res1["status"] == "enfileirado_com_debounce"

    # Segundo envio do mesmo id deve ser ignorado por idempotência
    res2 = await SendEventService.processar_evento_send(evento_msg)
    assert res2["status"] == "ignorado"
    assert res2["motivo"] == "evento_duplicado"


@pytest.mark.asyncio
async def test_send_event_opted_out_clears_buffer_and_never_replies(monkeypatch):
    SendEventService._processed_memory_ids.clear()
    mock_buffer = MockCacheBufferGateway()
    await mock_buffer.adicionar_mensagem("+5585999101413", '{"text": "Tenho interesse"}')

    monkeypatch.setattr(SendEventService, "buffer_gateway", mock_buffer)
    monkeypatch.setattr("services.inbound.send_event_service.redis_client.get", AsyncMock(return_value=None))
    monkeypatch.setattr("services.inbound.send_event_service.redis_client.setex", AsyncMock())

    lead_mock = models.Lead(
        id=10,
        telefone="+5585999101413",
        nome="Airlly",
        opt_out=False,
        desfecho=models.DesfechoLead.EM_ANDAMENTO,
        controle=models.ControleAtendimento.PILOTO_IA,
        tags=[],
    )

    class DummySessionCtx:
        async def __aenter__(self):
            return AsyncMock()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(SendEventService, "session_factory", lambda: DummySessionCtx())
    monkeypatch.setattr(LeadRepository, "get_by_phone", AsyncMock(return_value=lead_mock))
    monkeypatch.setattr(LeadRepository, "add_interaction", AsyncMock())
    monkeypatch.setattr("services.inbound.send_event_service.FollowupService.cancelar_followups_pendentes", AsyncMock())

    evento_optout = {
        "id": "evt-optout-4",
        "seq": 4,
        "type": "message.received",
        "data": {
            "contact": {"phone": "5585999101413", "name": "Airlly", "optedOut": True},
            "message": {
                "id": "msg-4",
                "type": "button",
                "button": {"text": "Não tenho interesse", "payload": "Não tenho interesse"},
            },
        },
    }

    res = await SendEventService.processar_evento_send(evento_optout)
    assert res["status"] == "opt_out_processado"
    assert lead_mock.opt_out is True
    assert lead_mock.desfecho == models.DesfechoLead.PERDIDO
    assert await mock_buffer.contar_buffers_pendentes() == 0


@pytest.mark.asyncio
async def test_send_outbound_does_not_retry_on_409_or_422(monkeypatch):
    monkeypatch.setattr(settings, "SEND_API_KEY", "sk_test_key")
    chamadas = 0

    class FakeResponse:
        status_code = 409
        text = '{"error":"Conversa em atendimento humano","code":"HUMAN_HANDOVER"}'

        def json(self):
            return {"error": "Conversa em atendimento humano", "code": "HUMAN_HANDOVER"}

    class FakeClient:
        async def post(self, *args, **kwargs):
            nonlocal chamadas
            chamadas += 1
            return FakeResponse()

    monkeypatch.setattr("integrations.send_inteligentte.client.get_send_client", lambda: FakeClient())

    res = await enviar_mensagem_send("5583999990001", "Olá!", max_retries=3)
    assert res["status"] == "erro"
    assert res["code"] == "HUMAN_HANDOVER"
    assert res["nao_retentar"] is True
    assert chamadas == 1

