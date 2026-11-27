"""Puertos (interfaces) de la arquitectura de puertos y adaptadores.

El motor, la bandeja y la interfaz SOLO conocen estos puertos. Los adaptadores
(banco simulado, Belo API, Belo MCP, fakes) los implementan. Cambiar de banco es
cambiar BANCO_MODO en el .env, sin tocar el resto del código.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Protocol, runtime_checkable

from core.modelos import Cotizacion, Moneda, Movimiento, Operacion, Rendimiento, Resultado, Saldo


@runtime_checkable
class BancoPort(Protocol):
    """Lo que el agente necesita de un banco.

    Los nombres imitan las herramientas del MCP de Belo:
    - saldos()       -> consulta de saldos
    - cotizacion()   -> cambio de divisas (cotización)
    - rendimiento()  -> rendimientos
    - ejecutar()     -> aprobación / ejecución de transacciones
    - movimientos()  -> historial de movimientos
    """

    def saldos(self) -> list[Saldo]:
        """Saldos actuales en cada moneda (USD, COP, USDT)."""
        ...

    def cotizacion(self, desde: Moneda, hacia: Moneda) -> Cotizacion:
        """Cotización de hoy. `tasa` va SIN spread; el spread va aparte."""
        ...

    def rendimiento(self, moneda: Moneda) -> Rendimiento:
        """Rendimiento anual que paga la moneda (ej. USDT)."""
        ...

    def ejecutar(self, op: Operacion) -> Resultado:
        """Ejecuta una operación. IDEMPOTENTE por op.id:
        si el id ya se ejecutó, devuelve ok=False y no cambia ningún saldo."""
        ...

    def movimientos(self) -> list[Movimiento]:
        """Historial de movimientos, del más antiguo al más reciente."""
        ...


@runtime_checkable
class MercadoPort(Protocol):
    """Datos de mercado históricos (TRM)."""

    def historico(self, desde: Moneda, hacia: Moneda, dias: int) -> list[Cotizacion]:
        """Las últimas `dias` cotizaciones, ordenadas de la más antigua a la más reciente."""
        ...


@runtime_checkable
class Reloj(Protocol):
    """Reloj inyectable: permite simular el paso del tiempo en la demo y los tests."""

    def hoy(self) -> date:
        ...

    def ahora(self) -> datetime:
        """Fecha y hora en UTC (con tzinfo)."""
        ...
