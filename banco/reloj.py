"""Reloj simulado para la demo (Persona 1). Cumple core.puertos.Reloj."""

from __future__ import annotations

from datetime import date, datetime

P1 = "Persona 1 (banco): "


class RelojSimulado:
    """Reloj que arranca en `inicio` y avanza a mano para recorrer el mes en la demo.

    - hoy() -> date actual simulada.
    - ahora() -> datetime en UTC (con tzinfo=timezone.utc).
    - avanzar(dias): salta días (ej. del día 1 al día 8 para el primer tramo).
    - avanzar_segundos(s): para que venzan las solicitudes de la bandeja (60 s).
    """

    def __init__(self, inicio: date) -> None:
        self.inicio = inicio

    def hoy(self) -> date:
        raise NotImplementedError(P1 + "RelojSimulado.hoy")

    def ahora(self) -> datetime:
        raise NotImplementedError(P1 + "RelojSimulado.ahora")

    def avanzar(self, dias: int) -> None:
        raise NotImplementedError(P1 + "RelojSimulado.avanzar")

    def avanzar_segundos(self, s: float) -> None:
        raise NotImplementedError(P1 + "RelojSimulado.avanzar_segundos")
