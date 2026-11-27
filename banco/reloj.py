"""Reloj simulado para la demo (Persona 1). Cumple core.puertos.Reloj."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone


class RelojSimulado:
    """Reloj que arranca en `inicio` y avanza a mano para recorrer el mes en la demo.

    - hoy() -> date actual simulada (en UTC).
    - ahora() -> datetime en UTC (con tzinfo=timezone.utc).
    - avanzar(dias): salta días (ej. del día 1 al día 8 para el primer tramo).
    - avanzar_segundos(s): para que venzan las solicitudes de la bandeja (60 s).
    """

    def __init__(self, inicio: date | datetime) -> None:
        self.inicio = inicio
        if isinstance(inicio, datetime):
            self._ahora = (
                inicio.replace(tzinfo=timezone.utc)
                if inicio.tzinfo is None
                else inicio.astimezone(timezone.utc)
            )
        else:
            self._ahora = datetime.combine(inicio, time(12, 0), tzinfo=timezone.utc)

    def hoy(self) -> date:
        """Fecha actual simulada en UTC."""
        return self._ahora.date()

    def ahora(self) -> datetime:
        """Fecha y hora actual simulada en UTC (siempre con tzinfo=timezone.utc)."""
        return self._ahora

    def avanzar(self, dias: int) -> None:
        """Avanza el reloj la cantidad de días indicada."""
        self._ahora += timedelta(days=dias)

    def avanzar_segundos(self, s: float) -> None:
        """Avanza el reloj la cantidad de segundos indicada."""
        self._ahora += timedelta(seconds=s)
