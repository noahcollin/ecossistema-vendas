from datetime import datetime, timezone, timedelta, time
from typing import Optional

from core.config import settings


class BusinessHoursPolicy:
    """
    Política de domínio para cálculo e adequação de Horários Comerciais e Anti-Ban Pacing.
    Garante que nenhum contato ativo ocorra fora das janelas permitidas:
    - Seg a Sex: 08:30 às 18:30 (UTC-3)
    - Sábado: 09:00 às 12:30 (UTC-3)
    - Domingo: Fechado (postergado para Segunda 08:35)
    """

    OFFSET_BRASIL = timedelta(hours=-3)

    @staticmethod
    def _parse_hhmm(hhmm: str) -> time:
        h, m = map(int, hhmm.split(":"))
        return time(hour=h, minute=m)

    @classmethod
    def ajustar_para_horario_comercial(cls, dt_utc: datetime, indice_dispersao: int = 0) -> datetime:
        """
        Ajusta um datetime (UTC) para que seu equivalente em Brasília (UTC-3)
        esteja estritamente dentro da janela comercial permitida.
        
        Aplica dispersão determinística (Jitter) para evitar rajadas simultâneas
        quando múltiplos leads acumulam fora do expediente, garantindo que o jitter
        jamais empurre o disparo para além do fechamento da janela.
        """
        if dt_utc.tzinfo is not None:
            dt_utc = dt_utc.astimezone(timezone.utc).replace(tzinfo=None)

        dt_local = dt_utc + cls.OFFSET_BRASIL

        inicio_util = cls._parse_hhmm(settings.BUSINESS_HOURS_START)
        fim_util = cls._parse_hhmm(settings.BUSINESS_HOURS_END)
        inicio_sabado = cls._parse_hhmm(settings.BUSINESS_HOURS_SATURDAY_START)
        fim_sabado = cls._parse_hhmm(settings.BUSINESS_HOURS_SATURDAY_END)

        minutos_jitter = indice_dispersao * settings.FOLLOWUP_JITTER_STEP_MINUTES
        segundos_jitter = (indice_dispersao * 17) % 45
        delta_jitter = timedelta(minutes=minutos_jitter, seconds=segundos_jitter)

        # Candidato inicial somando o jitter
        candidato = dt_local + delta_jitter

        def esta_no_expediente(dt: datetime) -> bool:
            wd = dt.weekday()
            t = dt.time()
            if wd == 6:  # Domingo
                return False
            elif wd == 5:  # Sábado
                return inicio_sabado <= t <= fim_sabado
            else:  # Segunda a Sexta
                return inicio_util <= t <= fim_util

        if esta_no_expediente(candidato):
            ajustado_local = candidato
        else:
            wd = candidato.weekday()
            hora = candidato.time()

            # Domingo -> empurra para Segunda às 08:35 + jitter
            if wd == 6:
                base = datetime.combine(
                    candidato.date() + timedelta(days=1),
                    time(hour=8, minute=35)
                )
                ajustado_local = base + delta_jitter

            # Sábado
            elif wd == 5:
                if hora < inicio_sabado:
                    base = datetime.combine(candidato.date(), time(hour=9, minute=5))
                    ajustado_local = base + delta_jitter
                else:  # Após fechamento do sábado -> Segunda 08:35 + jitter
                    base = datetime.combine(
                        candidato.date() + timedelta(days=2),
                        time(hour=8, minute=35)
                    )
                    ajustado_local = base + delta_jitter

            # Segunda a Sexta
            else:
                if hora < inicio_util:
                    base = datetime.combine(candidato.date(), time(hour=8, minute=35))
                    ajustado_local = base + delta_jitter
                else:  # Após o fechamento do dia útil
                    if wd == 4:  # Sexta à noite -> empurra para Sábado de manhã
                        base = datetime.combine(
                            candidato.date() + timedelta(days=1),
                            time(hour=9, minute=5)
                        )
                    else:  # Seg a Qui à noite -> dia seguinte 08:35
                        base = datetime.combine(
                            candidato.date() + timedelta(days=1),
                            time(hour=8, minute=35)
                        )
                    ajustado_local = base + delta_jitter

        return ajustado_local - cls.OFFSET_BRASIL

    @classmethod
    def calcular_momento_disparo(cls, tentativa: int, base_time: Optional[datetime] = None) -> datetime:
        """
        Calcula o próximo momento de disparo somando o intervalo da tentativa
        e ajustando estritamente para a janela comercial.
        """
        agora = base_time or datetime.now(timezone.utc).replace(tzinfo=None)

        if tentativa == 1:
            horas = settings.FOLLOWUP_INTERVAL_1_HOURS
        elif tentativa == 2:
            horas = settings.FOLLOWUP_INTERVAL_2_HOURS
        else:
            horas = settings.FOLLOWUP_INTERVAL_3_HOURS

        dt_bruta = agora + timedelta(hours=horas)
        return cls.ajustar_para_horario_comercial(dt_bruta)
