from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from core.temporal import TemporalContextProvider

TZ_BR = ZoneInfo("America/Sao_Paulo")


def test_conversao_utc_para_brasilia():
    dt_utc = datetime(2026, 11, 13, 17, 50)  # 17:50 UTC = 14:50 BRT
    dt_br = TemporalContextProvider.agora_local(referencia_utc=dt_utc)
    assert dt_br.hour == 14
    assert dt_br.minute == 50
    assert TemporalContextProvider.formatar_timestamp_local(dt_utc) == "13/11 14:50"


def test_horarios_quinta_feira_com_antecedencia_suficiente():
    # Quinta-feira, 12/11/2026 às 12:30 BRT -> 15h e 16h têm >= 2h de antecedência
    agora = datetime(2026, 11, 12, 12, 30, tzinfo=TZ_BR)
    slots = TemporalContextProvider.calcular_proximos_horarios_agendamento(
        agora=agora,
        quantidade=2,
        dias_ativos=[0, 1, 2, 3, 4],
    )
    assert slots == ["hoje 15h", "hoje 16h"]


def test_horarios_sexta_tarde_pula_fim_de_semana():
    # Sexta-feira, 13/11/2026 às 14:58 BRT (< 2h para 16h) -> pula Sábado e Domingo
    agora = datetime(2026, 11, 13, 14, 58, tzinfo=TZ_BR)
    slots = TemporalContextProvider.calcular_proximos_horarios_agendamento(
        agora=agora,
        quantidade=2,
        dias_ativos=[0, 1, 2, 3, 4],
    )
    assert slots == ["segunda 10h", "segunda 15h"]


def test_horarios_sexta_com_16h_disponivel():
    # Sexta-feira, 13/11/2026 às 13:30 BRT (>= 2h para 16h) -> hoje 16h e segunda 10h
    agora = datetime(2026, 11, 13, 13, 30, tzinfo=TZ_BR)
    slots = TemporalContextProvider.calcular_proximos_horarios_agendamento(
        agora=agora,
        quantidade=2,
        dias_ativos=[0, 1, 2, 3, 4],
    )
    assert slots == ["hoje 16h", "segunda 10h"]


def test_horarios_domingo_sugere_amanha():
    # Domingo, 15/11/2026 às 11:00 BRT -> amanhã 10h e amanhã 15h
    agora = datetime(2026, 11, 15, 11, 0, tzinfo=TZ_BR)
    slots = TemporalContextProvider.calcular_proximos_horarios_agendamento(
        agora=agora,
        quantidade=2,
        dias_ativos=[0, 1, 2, 3, 4],
    )
    assert slots == ["amanhã 10h", "amanhã 15h"]


def test_bloco_referencia_temporal_completo():
    # 13/11/2026 17:58 UTC = 14:58 BRT (sexta-feira)
    ref_utc = datetime(2026, 11, 13, 17, 58, tzinfo=timezone.utc)
    bloco = TemporalContextProvider.gerar_bloco_referencia_temporal(referencia_utc=ref_utc)
    assert "sexta-feira, 13/11/2026 às 14:58" in bloco
    assert "Amanhã: sábado, 14/11/2026" in bloco
    assert "segunda-feira (16/11)" in bloco
    assert "segunda 10h ou segunda 15h" in bloco
