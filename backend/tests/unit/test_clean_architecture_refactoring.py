"""
Testes Unitários da Reestruturação Clean Architecture, SOLID, Governança e Concorrência (v1.3.0).
Valida os novos contratos sem depender de instâncias externas de PostgreSQL ou Redis.
"""

import asyncio
from unittest.mock import AsyncMock
import pytest

import models
import schemas
from core.background import (
    spawn_background_task,
    get_active_background_tasks_count,
    drain_background_tasks,
)
from core.config import settings
from core.openai_client import is_openai_quota_error
from agents.deal_auditor_agent import _recortar_historico_auditoria
from repositories.lead_repository import LeadRepository
from schemas.settings import (
    OperacaoSettingsResponse,
    ProdutoItem,
    CadenciaConfig,
    HorarioComercialConfig,
    PacingConfig,
)
from services.handover.dashboard_service import DashboardService
from services.inbound.orchestrator import InboundService
from services.inbound.webhook_service import WebhookApplicationService
from services.settings import SettingsService
from tests.conftest import MockCacheBufferGateway, MockWhatsAppGateway


@pytest.mark.asyncio
async def test_background_task_registry_holds_strong_ref_and_cleans_up():
    """Garante que tasks disparadas em background mantêm referência forte e limpam o registro ao concluir."""
    concluido = asyncio.Event()

    async def worker_rapido():
        await asyncio.sleep(0.02)
        concluido.set()

    antes = get_active_background_tasks_count()
    task = spawn_background_task(worker_rapido(), name="teste_strong_ref")
    assert get_active_background_tasks_count() >= antes + 1

    await drain_background_tasks(timeout=2.0)
    assert concluido.is_set()
    assert task.done()


def test_is_openai_quota_error_centralized_detection():
    """Valida o helper DRY de detecção de esgotamento de cota/créditos da OpenAI."""
    err_quota = Exception(
        "Error code: 429 - {'error': {'message': 'You exceeded your current quota, check billing', 'code': 'insufficient_quota'}}"
    )
    err_rede = Exception("Connection reset by peer")

    assert is_openai_quota_error(err_quota) is True
    assert is_openai_quota_error(err_rede) is False


def test_deal_auditor_window_slicing_preserves_opening_and_tail():
    """Garante que conversas longas preservam as 4 mensagens iniciais e as mais recentes dentro do teto FinOps."""
    historico = [
        models.Interacao(id=i, lead_id=1, origem=models.InteracaoOrigem.CLIENTE, texto=f"msg_{i}")
        for i in range(1, 26)
    ]

    recortado, omitidas = _recortar_historico_auditoria(historico, limite_maximo=10)

    assert len(recortado) == 10
    assert omitidas == 15
    assert [m.id for m in recortado[:4]] == [1, 2, 3, 4]
    assert [m.id for m in recortado[4:]] == [20, 21, 22, 23, 24, 25]


@pytest.mark.asyncio
async def test_webhook_application_service_filters_and_enqueues(monkeypatch):
    """
    Valida as regras de triagem do WebhookApplicationService desacoplado do router HTTP:
    1. Ignora grupos (@g.us);
    2. Ignora eco de mensagens próprias (fromMe=True com marcador bot no buffer);
    3. Respeita trava Sandbox;
    4. Enfileira mensagens válidas no CacheBufferProtocol injetado.
    """
    mock_buffer = MockCacheBufferGateway()
    monkeypatch.setattr(WebhookApplicationService, "buffer_gateway", mock_buffer)

    # Evita disparo real do sleep de debounce durante o teste unitário
    tasks_disparadas: list[str] = []

    def fake_spawn(coro, *, name=None):
        tasks_disparadas.append(name or "unnamed")
        coro.close()
        return asyncio.create_task(asyncio.sleep(0))

    monkeypatch.setattr("services.inbound.webhook_service.spawn_background_task", fake_spawn)

    # 1. Grupo deve ser ignorado
    payload_grupo = schemas.UazapiPayload(
        chat=schemas.UazapiChat(phone="120363049999@g.us", isGroup=True),
        message=schemas.UazapiMessage(text="Mensagem em grupo"),
    )
    res_grupo = await WebhookApplicationService.processar_evento_uazapi(payload_grupo)
    assert res_grupo["status"] == "ignorado"
    assert res_grupo["motivo"] == "mensagem_de_grupo_ou_canal"

    # 2. Eco do próprio bot (fromMe=True com marcador registrado) deve ser ignorado
    await mock_buffer.registrar_marcador_bot("msg_painel_123")
    payload_bot = schemas.UazapiPayload(
        chat=schemas.UazapiChat(phone="5583999991111"),
        message=schemas.UazapiMessage(id="owner:msg_painel_123", fromMe=True, text="Oi, tudo bem?"),
    )
    res_bot = await WebhookApplicationService.processar_evento_uazapi(payload_bot)
    assert res_bot["status"] == "ignorado"
    assert res_bot["motivo"] == "mensagem_do_proprio_bot"

    # 3. Trava Sandbox ativa bloqueia número fora da whitelist
    monkeypatch.setattr(settings, "SANDBOX_MODE", True)
    monkeypatch.setattr(settings, "WHITELIST_PHONE_SUFFIX", "7777")
    payload_fora = schemas.UazapiPayload(
        chat=schemas.UazapiChat(phone="5583999990000", name="Visitante"),
        message=schemas.UazapiMessage(text="Quero orçamento"),
    )
    res_sandbox = await WebhookApplicationService.processar_evento_uazapi(payload_fora)
    assert res_sandbox["status"] == "ignorado"
    assert res_sandbox["motivo"] == "numero_fora_da_whitelist_de_teste"

    # 4. Mensagem válida (Sandbox desligado) entra no buffer e agenda debounce
    monkeypatch.setattr(settings, "SANDBOX_MODE", False)
    res_ok = await WebhookApplicationService.processar_evento_uazapi(payload_fora)
    assert res_ok["status"] == "enfileirado_com_debounce"
    assert await mock_buffer.contar_buffers_pendentes() == 1
    assert any(t.startswith("debounce_") for t in tasks_disparadas)


@pytest.mark.asyncio
async def test_settings_service_runtime_sync_catalog_prompt_and_redis_purge():
    """
    Valida que a Sala de Máquinas:
    1. Sincroniza runtime L1 e `core.config.settings` corretamente;
    2. Monta o resumo vivo do catálogo apenas com produtos ativos;
    3. Expurga filas voláteis via CacheBufferProtocol.
    """
    cache_original = SettingsService.obter_cache_memoria()
    debounce_original = settings.DEBOUNCE_SECONDS

    try:
        nova_cfg = OperacaoSettingsResponse(
            produtos=[
                ProdutoItem(
                    id="agente-sdr",
                    nome="Agente SDR Pro",
                    descricao="Qualificação 24/7",
                    modelo_comercial="SaaS + Setup",
                    qualificacao_minima="> 20 leads/dia",
                    diretriz_venda="Destacar ROI em 30 dias",
                    preco_base_mensal=1990.0,
                    taxa_setup=3500.0,
                    ativo=True,
                ),
                ProdutoItem(
                    id="produto-legado",
                    nome="Plano Antigo",
                    preco_base_mensal=500.0,
                    taxa_setup=0.0,
                    ativo=False,
                ),
            ],
            cadencia=CadenciaConfig(
                ativo=True,
                max_tentativas=3,
                intervalo_horas=4,
                intervalos_toques=[4, 24, 72],
            ),
            horario_comercial=HorarioComercialConfig(
                inicio_hora=9,
                fim_hora=19,
                dias_uteis=[0, 1, 2, 3, 4],
            ),
            pacing=PacingConfig(
                simular_digitacao=True,
                limiar_proativo=6,
                limiar_decisivo=14,
                limiar_max_finops=24,
            ),
            debounce_segundos=12.5,
            modo_24h_inbound=True,
            ia_silenciada_global=False,
            mensagem_inatividade="Encerramento padrão.",
        )

        SettingsService._sincronizar_runtime(nova_cfg)
        assert settings.DEBOUNCE_SECONDS == 12.5
        assert settings.BUSINESS_HOURS_START == "09:00"
        assert settings.BUSINESS_HOURS_END == "19:00"
        assert settings.FOLLOWUP_INTERVAL_1_HOURS == 4.0
        assert settings.FOLLOWUP_INTERVAL_2_HOURS == 24.0
        assert settings.FOLLOWUP_INTERVAL_3_HOURS == 72.0
        assert settings.PACING_THRESHOLD_MAX == 24

        resumo = SettingsService.montar_resumo_catalogo_prompt()
        assert "Agente SDR Pro" in resumo
        assert "Destacar ROI em 30 dias" in resumo
        assert "Plano Antigo" not in resumo

        mock_buffer = MockCacheBufferGateway()
        await mock_buffer.adicionar_mensagem("+5583999990001", '{"text": "oi"}')
        await mock_buffer.adquirir_lock("lock:inbound:+5583999990001")
        purge_res = await SettingsService.expurgar_filas_redis(buffer_gateway=mock_buffer)
        assert purge_res.status == "sucesso"
        assert purge_res.chaves_removidas >= 2
        assert await mock_buffer.contar_buffers_pendentes() == 0
    finally:
        SettingsService._sincronizar_runtime(cache_original)
        settings.DEBOUNCE_SECONDS = debounce_original


@pytest.mark.asyncio
async def test_inbound_kill_switch_persists_message_and_pauses_ai(monkeypatch):
    """
    Quando `ia_silenciada_global=True` (Kill-Switch da Sala de Máquinas),
    o InboundService deve persistir a mensagem do cliente, cancelar follow-ups pendentes
    e NÃO enviar presença ou acionar agentes da OpenAI.
    """
    cache_original = SettingsService.obter_cache_memoria()
    mock_gw = MockWhatsAppGateway()
    monkeypatch.setattr(InboundService, "whatsapp_gateway", mock_gw)

    lead = models.Lead(
        id=42,
        telefone="+5583999994242",
        nome="Maria",
        controle=models.ControleAtendimento.PILOTO_IA,
        opt_out=False,
        tags=[],
    )
    mock_db = AsyncMock()
    add_interacao_mock = AsyncMock()
    cancelar_fup_mock = AsyncMock()
    analisar_mock = AsyncMock()

    monkeypatch.setattr(InboundService, "_obter_ou_criar_lead", AsyncMock(return_value=lead))
    monkeypatch.setattr(LeadRepository, "add_interaction", add_interacao_mock)
    monkeypatch.setattr("services.inbound.orchestrator.FollowupService.cancelar_followups_pendentes", cancelar_fup_mock)
    monkeypatch.setattr("agents.analisar_lead_e_fsm", analisar_mock)

    try:
        silenciado = cache_original.model_copy(update={"ia_silenciada_global": True})
        SettingsService._sincronizar_runtime(silenciado)

        await InboundService._executar_pipeline_atendimento(
            db=mock_db,
            telefone="+5583999994242",
            nome_contato="Maria",
            texto_consolidado="Olá, gostaria de saber preços",
        )

        add_interacao_mock.assert_awaited_once()
        cancelar_fup_mock.assert_awaited_once_with(mock_db, 42)
        analisar_mock.assert_not_awaited()
        assert len(mock_gw.presencas_enviadas) == 0
        assert len(mock_gw.mensagens_enviadas) == 0
    finally:
        SettingsService._sincronizar_runtime(cache_original)


@pytest.mark.asyncio
async def test_inbound_clears_stale_motivo_perda_when_deal_resumes(monkeypatch):
    """Garante que um lead reengajado (EM_ANDAMENTO) tem `motivo_perda` legado limpo antes do commit."""
    mock_gw = MockWhatsAppGateway()
    monkeypatch.setattr(InboundService, "whatsapp_gateway", mock_gw)

    lead = models.Lead(
        id=77,
        telefone="+5583999997777",
        nome="Carlos",
        etapa_funil=models.EtapaFunil.QUALIFICACAO,
        desfecho=models.DesfechoLead.PERDIDO,
        motivo_perda="Preço acima do orçamento",
        controle=models.ControleAtendimento.PILOTO_IA,
        temperatura=models.TemperaturaLead.FRIO,
        tags=[],
    )

    analise_retomada = schemas.LeadAnalysisOutput(
        resumo_perfil="Cliente voltou após aprovar verba.",
        etapa_sugerida=models.EtapaFunil.NEGOCIACAO,
        desfecho_sugerido=models.DesfechoLead.EM_ANDAMENTO,
        transbordo_sugerido=False,
        temperatura_sugerida=models.TemperaturaLead.QUENTE,
        justificativa="Retomada comercial",
        dados_qualificacao=schemas.DadosQualificacao(segmento="Clínica Médica"),
    )

    mock_db = AsyncMock()
    monkeypatch.setattr("agents.analisar_lead_e_fsm", AsyncMock(return_value=analise_retomada))
    monkeypatch.setattr("agents.gerar_resposta_vendedor", AsyncMock(return_value="Que ótima notícia, Carlos!"))
    monkeypatch.setattr(
        "services.inbound.orchestrator.ConversationPacingService.resetar_etapa",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "services.inbound.orchestrator.ConversationPacingService.avaliar_e_incrementar",
        AsyncMock(
            return_value=type(
                "PacingEvalStub",
                (),
                {
                    "deve_encerrar_por_estagnacao": False,
                    "diretriz_proatividade": None,
                    "mensagens_na_etapa": 1,
                    "mensagem_despedida_humana": None,
                },
            )()
        ),
    )
    monkeypatch.setattr(LeadRepository, "add_interaction", AsyncMock())
    monkeypatch.setattr(LeadRepository, "recarregar_lead", AsyncMock(return_value=lead))
    monkeypatch.setattr(
        "services.inbound.orchestrator.FollowupService.agendar_proximo_followup",
        AsyncMock(),
    )

    await InboundService._processar_cognicao_e_resposta(
        db=mock_db,
        lead=lead,
        telefone="+5583999997777",
        nome_contato="Carlos",
        texto_consolidado="Consegui aprovar o orçamento, vamos retomar?",
        historico_recente=[],
    )

    assert lead.desfecho == models.DesfechoLead.EM_ANDAMENTO
    assert lead.motivo_perda is None
    assert len(mock_gw.mensagens_enviadas) == 1


@pytest.mark.asyncio
async def test_dashboard_service_sends_human_message_via_injected_protocols(monkeypatch):
    """
    Valida que DashboardService.enviar_mensagem_humana_painel respeita DIP:
    usa WhatsAppGatewayProtocol + CacheBufferProtocol injetados, grava marcador anti-eco,
    transiciona o lead para HUMANO_ASSUMIU e cancela follow-ups pendentes.
    """
    mock_gw = MockWhatsAppGateway()
    mock_buffer = MockCacheBufferGateway()
    monkeypatch.setattr(DashboardService, "whatsapp_gateway", mock_gw)
    monkeypatch.setattr(DashboardService, "buffer_gateway", mock_buffer)

    lead = models.Lead(
        id=15,
        telefone="+5583988881515",
        nome="Fernanda",
        controle=models.ControleAtendimento.TRANSBORDO_SOLICITADO,
        tags=["REQUER_ATENCAO"],
    )
    interacao_criada = models.Interacao(
        id=501,
        lead_id=15,
        origem=models.InteracaoOrigem.HUMANO,
        texto="Olá Fernanda, sou o especialista responsável!",
    )

    mock_db = AsyncMock()
    cancelar_mock = AsyncMock()
    monkeypatch.setattr(LeadRepository, "get_by_id", AsyncMock(return_value=lead))
    monkeypatch.setattr(LeadRepository, "add_interaction", AsyncMock(return_value=interacao_criada))
    monkeypatch.setattr("services.handover.dashboard_service.FollowupService.cancelar_followups_pendentes", cancelar_mock)

    resultado = await DashboardService.enviar_mensagem_humana_painel(
        db=mock_db,
        lead_id=15,
        texto="Olá Fernanda, sou o especialista responsável!",
        atendente="Closer Sênior",
    )

    assert resultado.id == 501
    assert len(mock_gw.mensagens_enviadas) == 1
    assert await mock_buffer.verificar_marcador_bot("mock_msg_1") is True
    assert lead.controle == models.ControleAtendimento.HUMANO_ASSUMIU
    assert "EM_ATENDIMENTO_HUMANO" in lead.tags
    assert "REQUER_ATENCAO" not in lead.tags
    cancelar_mock.assert_awaited_once_with(mock_db, 15)
