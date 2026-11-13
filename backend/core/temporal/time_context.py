"""
Provedor Determinístico de Contexto Temporal e Disponibilidade de Agenda.
Centraliza cálculos de fuso horário (America/Sao_Paulo), calendário dos próximos dias
e geração de horários válidos para agendamento sem depender de aritmética de LLMs.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

DIAS_SEMANA_COMPLETO = [
    "segunda-feira",
    "terça-feira",
    "quarta-feira",
    "quinta-feira",
    "sexta-feira",
    "sábado",
    "domingo",
]

DIAS_SEMANA_CURTO = [
    "segunda",
    "terça",
    "quarta",
    "quinta",
    "sexta",
    "sábado",
    "domingo",
]


class TemporalContextProvider:
    """
    Fonte única de verdade temporal para todos os agentes de IA do ecossistema.
    Converte referências UTC para o fuso operacional configurado (padrão: America/Sao_Paulo)
    e pré-calcula opções válidas de agendamento.
    """

    DEFAULT_TZ = "America/Sao_Paulo"
    DEFAULT_DIAS_ATIVOS = [0, 1, 2, 3, 4]  # Segunda a Sexta
    SLOTS_PADRAO_HORA = [10, 15, 16]
    ANTECEDENCIA_MINIMA_HOJE_HORAS = 2

    @classmethod
    def _obter_config_horario(cls) -> tuple[str, list[int], int, int]:
        """Obtém fuso, dias ativos e janela comercial do cache de Settings com fallback seguro."""
        try:
            from services.settings import SettingsService
            hc = SettingsService.obter_cache_memoria().horario_comercial
            fuso = hc.fuso_horario or cls.DEFAULT_TZ
            dias = list(hc.dias_semana) if hc.dias_semana else list(cls.DEFAULT_DIAS_ATIVOS)
            inicio = int(hc.inicio_hora)
            fim = int(hc.fim_hora)
            return fuso, dias, inicio, fim
        except Exception:
            return cls.DEFAULT_TZ, list(cls.DEFAULT_DIAS_ATIVOS), 8, 18

    @classmethod
    def agora_local(
        cls,
        referencia_utc: Optional[datetime] = None,
        fuso: Optional[str] = None,
    ) -> datetime:
        """Retorna o datetime atual (ou convertido de referencia_utc) no fuso operacional."""
        tz_nome = fuso or cls._obter_config_horario()[0]
        try:
            tz = ZoneInfo(tz_nome)
        except Exception:
            tz = ZoneInfo(cls.DEFAULT_TZ)

        if referencia_utc is None:
            return datetime.now(tz)

        if referencia_utc.tzinfo is None:
            referencia_utc = referencia_utc.replace(tzinfo=timezone.utc)
        return referencia_utc.astimezone(tz)

    @classmethod
    def formatar_timestamp_local(
        cls,
        dt: Optional[datetime],
        fuso: Optional[str] = None,
    ) -> str:
        """Formata um datetime (UTC naive ou aware) para 'dd/mm HH:MM' no fuso local."""
        if dt is None:
            return ""
        local_dt = cls.agora_local(referencia_utc=dt, fuso=fuso)
        return local_dt.strftime("%d/%m %H:%M")

    @classmethod
    def calcular_proximos_horarios_agendamento(
        cls,
        agora: Optional[datetime] = None,
        quantidade: int = 2,
        dias_ativos: Optional[list[int]] = None,
    ) -> list[str]:
        """
        Calcula deterministicamente os próximos horários válidos para reunião de 20 min:
        - Para hoje: exige pelo menos 2h de antecedência e horário entre 9h e 17h.
        - Para os próximos dias: respeita os dias úteis configurados (padrão Seg-Sex),
          usando 'amanhã' para D+1 e o nome do dia da semana a partir de D+2.
        """
        fuso_cfg, dias_cfg, inicio_cfg, fim_cfg = cls._obter_config_horario()
        agora_loc = agora if agora is not None else cls.agora_local(fuso=fuso_cfg)
        dias_permitidos = set(dias_ativos if dias_ativos is not None else dias_cfg)
        if not dias_permitidos:
            dias_permitidos = set(cls.DEFAULT_DIAS_ATIVOS)

        hora_min = max(9, inicio_cfg)
        hora_max = min(17, fim_cfg - 1) if fim_cfg > 9 else 17
        slots_dia = [h for h in cls.SLOTS_PADRAO_HORA if hora_min <= h <= hora_max]
        if not slots_dia:
            slots_dia = [10, 15]

        opcoes: list[str] = []
        limite_hoje = agora_loc + timedelta(hours=cls.ANTECEDENCIA_MINIMA_HOJE_HORAS)

        for offset_dias in range(0, 10):
            data_alvo = (agora_loc + timedelta(days=offset_dias)).date()
            wd = data_alvo.weekday()
            if wd not in dias_permitidos:
                continue

            if offset_dias == 0:
                rotulo_dia = "hoje"
            elif offset_dias == 1:
                rotulo_dia = "amanhã"
            else:
                rotulo_dia = DIAS_SEMANA_CURTO[wd]

            for hora in slots_dia:
                candidato = agora_loc.replace(
                    year=data_alvo.year,
                    month=data_alvo.month,
                    day=data_alvo.day,
                    hour=hora,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                if offset_dias == 0 and candidato < limite_hoje:
                    continue

                opcoes.append(f"{rotulo_dia} {hora}h")
                if len(opcoes) >= quantidade:
                    return opcoes

        return opcoes

    @classmethod
    def proximos_dias_uteis(
        cls,
        agora: Optional[datetime] = None,
        quantidade: int = 3,
        dias_ativos: Optional[list[int]] = None,
    ) -> list[str]:
        """Lista os próximos N dias úteis formatados como 'segunda-feira (16/11)'."""
        fuso_cfg, dias_cfg, _, _ = cls._obter_config_horario()
        agora_loc = agora if agora is not None else cls.agora_local(fuso=fuso_cfg)
        dias_permitidos = set(dias_ativos if dias_ativos is not None else dias_cfg)
        if not dias_permitidos:
            dias_permitidos = set(cls.DEFAULT_DIAS_ATIVOS)

        resultado: list[str] = []
        for offset in range(1, 14):
            dt = agora_loc + timedelta(days=offset)
            wd = dt.weekday()
            if wd in dias_permitidos:
                resultado.append(f"{DIAS_SEMANA_COMPLETO[wd]} ({dt.strftime('%d/%m')})")
                if len(resultado) >= quantidade:
                    break
        return resultado

    @classmethod
    def gerar_bloco_referencia_temporal(cls, referencia_utc: Optional[datetime] = None) -> str:
        """
        Gera o bloco padronizado de referência temporal no horário oficial de Brasília
        para injeção nos prompts de todos os agentes (Closer, Follow-up e Analista).
        """
        agora = cls.agora_local(referencia_utc=referencia_utc)
        amanha = agora + timedelta(days=1)

        dia_hoje = DIAS_SEMANA_COMPLETO[agora.weekday()]
        dia_amanha = DIAS_SEMANA_COMPLETO[amanha.weekday()]
        dias_uteis = cls.proximos_dias_uteis(agora=agora, quantidade=3)
        horarios_sugeridos = cls.calcular_proximos_horarios_agendamento(agora=agora, quantidade=2)

        horarios_str = " ou ".join(horarios_sugeridos) if len(horarios_sugeridos) >= 2 else (horarios_sugeridos[0] if horarios_sugeridos else "amanhã 10h")
        dias_uteis_str = ", ".join(dias_uteis)

        return (
            f"\n[REFERÊNCIA TEMPORAL ATUAL (Horário de Brasília - America/Sao_Paulo)]:\n"
            f"- Agora: {dia_hoje}, {agora.strftime('%d/%m/%Y às %H:%M')}.\n"
            f"- Amanhã: {dia_amanha}, {amanha.strftime('%d/%m/%Y')}.\n"
            f"- Próximos dias úteis de atendimento: {dias_uteis_str}.\n"
            f"- Próximos dois horários válidos pré-calculados para agendamento (priorize estes): {horarios_str}."
        )
