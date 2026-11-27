"""Dobles de prueba que cumplen los puertos leyendo fixtures/.

Sirven para que la Persona 2 (motor) y la Persona 3 (bandeja e interfaz) trabajen
sin esperar al banco de la Persona 1. Compartido: no se cambia sin avisar.
"""

from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from core.modelos import (
    Cotizacion,
    Moneda,
    Movimiento,
    Operacion,
    Politica,
    Propuesta,
    Rendimiento,
    Resultado,
    Saldo,
    Solicitud,
)

RAIZ = Path(__file__).resolve().parent.parent
FIXTURES = RAIZ / "fixtures"
RUTA_POLITICA = RAIZ / "motor" / "politica.yaml"

# Fecha de la demo: el día en que a Laura le llega el pago.
INICIO_DEMO = datetime(2026, 11, 1, 13, 0, 20, tzinfo=timezone.utc)


def leer_fixture(nombre: str) -> Any:
    return json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- cargadores


def cargar_ingreso_ejemplo() -> Movimiento:
    return Movimiento.model_validate(leer_fixture("ingreso.json"))


def cargar_cotizaciones_ejemplo() -> list[Cotizacion]:
    return [Cotizacion.model_validate(c) for c in leer_fixture("cotizaciones_30d.json")]


def cargar_rendimiento_ejemplo() -> Rendimiento:
    return Rendimiento.model_validate(leer_fixture("rendimiento.json"))


def cargar_propuesta_ejemplo() -> Propuesta:
    return Propuesta.model_validate(leer_fixture("propuesta.json"))


def cargar_solicitudes_ejemplo() -> list[Solicitud]:
    return [Solicitud.model_validate(s) for s in leer_fixture("solicitudes.json")]


def cargar_politica_ejemplo() -> Politica:
    """Lee motor/politica.yaml tal cual (sin lógica). La versión 'de verdad' es motor.politica.cargar_politica."""
    return Politica.model_validate(yaml.safe_load(RUTA_POLITICA.read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- dobles


class RelojFalso:
    """Reloj fijo que solo avanza cuando se le pide. Cumple core.puertos.Reloj."""

    def __init__(self, inicio: datetime | date = INICIO_DEMO) -> None:
        if isinstance(inicio, datetime):
            self._ahora = inicio if inicio.tzinfo else inicio.replace(tzinfo=timezone.utc)
        else:
            self._ahora = datetime.combine(inicio, time(12, 0), tzinfo=timezone.utc)

    def hoy(self) -> date:
        return self._ahora.date()

    def ahora(self) -> datetime:
        return self._ahora

    def avanzar(self, dias: int) -> None:
        self._ahora += timedelta(days=dias)

    def avanzar_segundos(self, s: float) -> None:
        self._ahora += timedelta(seconds=s)


class MercadoFalso:
    """Histórico desde fixtures/cotizaciones_30d.json. Cumple core.puertos.MercadoPort."""

    def __init__(self) -> None:
        self._cotizaciones = cargar_cotizaciones_ejemplo()

    def historico(self, desde: Moneda, hacia: Moneda, dias: int) -> list[Cotizacion]:
        filtradas = [c for c in self._cotizaciones if c.desde == desde and c.hacia == hacia]
        return filtradas[-dias:] if dias > 0 else []


class BancoFalso:
    """Banco en memoria que lee fixtures. Cumple core.puertos.BancoPort.

    - ejecutar() siempre devuelve ok=True y guarda la operación en memoria.
    - Rechaza (ok=False) un id repetido: idempotencia.
    - NO mueve saldos: eso es trabajo del BancoSimulado (Persona 1).
    """

    def __init__(self) -> None:
        self._saldos = [Saldo.model_validate(s) for s in leer_fixture("saldos.json")]
        self._cotizaciones = cargar_cotizaciones_ejemplo()
        self._rendimiento = cargar_rendimiento_ejemplo()
        self._movimientos: list[Movimiento] = [cargar_ingreso_ejemplo()]
        self.ejecutadas: dict[str, Operacion] = {}

    def saldos(self) -> list[Saldo]:
        return [s.model_copy() for s in self._saldos]

    def cotizacion(self, desde: Moneda, hacia: Moneda) -> Cotizacion:
        for c in reversed(self._cotizaciones):
            if c.desde == desde and c.hacia == hacia:
                return c
        raise ValueError(f"Sin cotización {desde}->{hacia} en los fixtures")

    def rendimiento(self, moneda: Moneda) -> Rendimiento:
        if moneda != self._rendimiento.moneda:
            raise ValueError(f"Sin rendimiento para {moneda} en los fixtures")
        return self._rendimiento

    def ejecutar(self, op: Operacion) -> Resultado:
        if op.id in self.ejecutadas:
            return Resultado(operacion_id=op.id, ok=False, mensaje="Operación ya ejecutada (id repetido)")
        self.ejecutadas[op.id] = op
        self._movimientos.append(
            Movimiento(
                fecha=op.fecha_programada,
                tipo=op.tipo,
                moneda=op.desde,
                monto=op.monto,
                descripcion=f"[fake] {op.tipo} {op.categoria} {op.desde}->{op.hacia or ''}",
            )
        )
        return Resultado(operacion_id=op.id, ok=True, mensaje="Ejecutada (banco falso)")

    def movimientos(self) -> list[Movimiento]:
        return list(self._movimientos)
