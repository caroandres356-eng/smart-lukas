"""Banco simulado (Persona 1). Cumple core.puertos.BancoPort.

Imita a Belo mientras no tengamos acceso a su API/MCP.

Fórmula de conversión del día d (USD o USDT -> COP):
    COP = monto × TRM_d × (1 − spread)          spread simulado de Belo = 0.01
Conversión USD -> USDT: 1 a 1 (sin spread, simplificación de la demo).

Rendimiento del USDT:
    cada día: saldo_usdt *= (1 + tasa_anual / 365)   tasa simulada = 0.10
    y se registra un Movimiento tipo "rendimiento".

Idempotencia:
    ejecutar(op) guarda op.id (en memoria y/o en banco.registro.Registro).
    Si el id ya se ejecutó -> Resultado(ok=False, mensaje="ya ejecutada") y NO cambia saldos.
    Si no hay saldo suficiente -> ok=False con el motivo.

Todos los Saldo/Cotizacion/Rendimiento devuelven fuente="simulado".
"""

from __future__ import annotations

from decimal import Decimal

from core.modelos import Cotizacion, Moneda, Movimiento, Operacion, Rendimiento, Resultado, Saldo
from core.puertos import Reloj

P1 = "Persona 1 (banco): "


class BancoSimulado:
    def __init__(self, reloj: Reloj) -> None:
        self.reloj = reloj

    def saldos(self) -> list[Saldo]:
        """Saldos USD, COP y USDT actuales."""
        raise NotImplementedError(P1 + "BancoSimulado.saldos")

    def cotizacion(self, desde: Moneda, hacia: Moneda) -> Cotizacion:
        """TRM del día reloj.hoy() (desde banco.mercado) con spread 0.01."""
        raise NotImplementedError(P1 + "BancoSimulado.cotizacion")

    def rendimiento(self, moneda: Moneda) -> Rendimiento:
        """USDT -> tasa_anual 0.10. Otras monedas -> 0."""
        raise NotImplementedError(P1 + "BancoSimulado.rendimiento")

    def ejecutar(self, op: Operacion) -> Resultado:
        """Aplica la conversión/pago con la fórmula de arriba. Idempotente por op.id."""
        raise NotImplementedError(P1 + "BancoSimulado.ejecutar")

    def movimientos(self) -> list[Movimiento]:
        raise NotImplementedError(P1 + "BancoSimulado.movimientos")

    # ---- solo para la demo (no están en el puerto) ----

    def recibir_pago(self, monto_usd: Decimal) -> Movimiento:
        """Simula que llega un pago en USD: suma al saldo y registra un Movimiento 'ingreso'."""
        raise NotImplementedError(P1 + "BancoSimulado.recibir_pago")

    def aplicar_rendimiento_diario(self) -> Movimiento | None:
        """Aplica un día de rendimiento al saldo USDT (ver fórmula arriba)."""
        raise NotImplementedError(P1 + "BancoSimulado.aplicar_rendimiento_diario")
