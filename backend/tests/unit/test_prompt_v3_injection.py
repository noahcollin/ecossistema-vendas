"""
Testes unitários para validar a implantação do Prompt Eli v3 (closer_vendedor, followup,
analista, auditor e injeção de variáveis dinâmicas em sales_closer_agent).
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import models
from agents.prompts import (
    PROMPT_BASE_VENDEDOR,
    ORIENTACOES_POR_ESTAGIO,
    ORIENTACOES_FOLLOWUP,
    PROMPT_SISTEMA_ANALISTA,
    PROMPT_SISTEMA_AUDITOR,
)
from agents.sales_closer_agent import (
    _formatar_origem_lead,
    _montar_prompt_base_vendedor,
    _formatar_dados_ja_sabemos,
    _limpar_prefixo_timestamp,
    formatar_dialogo_para_chat,
)
from core.temporal import TemporalContextProvider

TZ_BR = ZoneInfo("America/Sao_Paulo")


def test_prompt_v3_variaveis_injetadas_sem_placeholders_sobrando():
    """Garante que {data_hora_atual}, {origem_lead} e {horarios_livres} são substituídos integralmente."""
    renderizado = _montar_prompt_base_vendedor(
        origem_canal="META_ADS",
        horarios_livres="hoje (quarta) 16h; amanhã (quinta) 10h, 11h, 15h",
    )
    assert "{data_hora_atual}" not in renderizado
    assert "{origem_lead}" not in renderizado
    assert "{horarios_livres}" not in renderizado
    assert "anúncio Meta Ads (clique para WhatsApp)" in renderizado
    assert "hoje (quarta) 16h; amanhã (quinta) 10h, 11h, 15h" in renderizado
    assert "(horário de Brasília)" in renderizado


def test_formatar_origem_lead_mapeamentos():
    assert _formatar_origem_lead("META_ADS") == "anúncio Meta Ads (clique para WhatsApp)"
    assert _formatar_origem_lead("WHATSAPP_DIRETO") == "contato direto no WhatsApp"
    assert _formatar_origem_lead(None) == "contato direto no WhatsApp"
    assert _formatar_origem_lead("campanha_outubro") == "campanha_outubro"


def test_orientacoes_estagio_e_followup_completos():
    for etapa in (
        models.EtapaFunil.NOVO_CONTATO,
        models.EtapaFunil.QUALIFICACAO,
        models.EtapaFunil.NEGOCIACAO,
        models.EtapaFunil.FECHAMENTO,
    ):
        assert etapa in ORIENTACOES_POR_ESTAGIO
        assert len(ORIENTACOES_POR_ESTAGIO[etapa].strip()) > 20

    assert set(ORIENTACOES_FOLLOWUP.keys()) == {1, 2, 3}
    assert "1 balão" in ORIENTACOES_FOLLOWUP[1]
    assert "35 palavras" in PROMPT_BASE_VENDEDOR
    assert "Hoje 16h ou amanhã 10h?" in PROMPT_SISTEMA_ANALISTA
    assert "35 palavras" in PROMPT_SISTEMA_AUDITOR


def test_formatar_dados_ja_sabemos():
    assert _formatar_dados_ja_sabemos(None) == ""
    texto = _formatar_dados_ja_sabemos({
        "ramo_atividade": "clínica odontológica",
        "canal_principal": "Instagram",
    })
    assert "clínica odontológica" in texto
    assert "Instagram" in texto
    assert "ainda não" in texto


def test_temporal_prompt_v3_sexta_noite_pula_fim_de_semana():
    agora_sexta_noite = datetime(2026, 11, 13, 19, 10, tzinfo=TZ_BR)
    data_str = TemporalContextProvider.formatar_data_hora_atual_prompt(referencia_utc=agora_sexta_noite)
    assert data_str == "sexta-feira, 13/11/2026, 19h10 (horário de Brasília)"

    livres = TemporalContextProvider.gerar_horarios_livres_prompt(
        agora=agora_sexta_noite,
        max_dias=2,
        dias_ativos=[0, 1, 2, 3, 4],
    )
    assert "hoje" not in livres
    assert "sábado" not in livres
    assert "domingo" not in livres
    assert livres.startswith("segunda ")
    assert "terça " in livres


def test_limpar_prefixo_timestamp_e_dialogo_sem_timestamp():
    assert (
        _limpar_prefixo_timestamp("[16/11 13:56] Hamburgueria, então.|||E por onde chegam?")
        == "Hamburgueria, então.|||E por onde chegam?"
    )
    interacoes = [
        models.Interacao(
            id=1,
            lead_id=1,
            origem=models.InteracaoOrigem.IA,
            texto="[16/11 13:55] Qual é o ramo da sua empresa?",
            criado_em=datetime(2026, 11, 16, 16, 55),
        ),
        models.Interacao(
            id=2,
            lead_id=1,
            origem=models.InteracaoOrigem.CLIENTE,
            texto="Eu tenho uma hamburgueria",
            criado_em=datetime(2026, 11, 16, 16, 56),
        ),
    ]
    msgs = formatar_dialogo_para_chat(interacoes)
    assert msgs == [
        {"role": "assistant", "content": "Qual é o ramo da sua empresa?"},
        {"role": "user", "content": "Eu tenho uma hamburgueria"},
    ]
