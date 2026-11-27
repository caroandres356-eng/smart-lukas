"""Decisor determinista (Persona 2): cada operación sale auto, requiere_aprobacion o bloqueada.

REGLAS, EN ESTE ORDEN (gana la primera que aplique):
    1) Hay una regla aprendida "bloquear" para (tipo, categoria)              -> bloqueada
    2) Hay una regla aprendida "permitir_hasta" para (tipo, categoria)
       y el monto cabe (monto <= monto_max_usd)                              -> auto
    3) La operación deja el saldo USD por debajo de colchon_usd               -> bloqueada
    4) monto > auto_max_usd_por_operacion                                    -> requiere_aprobacion
    5) acumulado_dia_usd + monto > auto_max_usd_por_dia                      -> requiere_aprobacion
    6) Si no aplica ninguna                                                  -> auto

El motivo SIEMPRE dice la regla y los números. Ejemplos:
    "450 USD supera el límite de 300 USD por operación"
    "Dejaría 150 USD, por debajo del colchón de 200 USD"
    "Acumulado del día 580 USD supera el límite de 500 USD por día"
    "Regla aprendida: permitir conversion de arriendo hasta 500 USD"

Montos en USDT se tratan como USD (1:1) para los límites. Las reglas 3 a 5 solo
cuentan operaciones cuyo `desde` es USD o USDT.

La IA NO participa aquí: montos y decisiones son 100 % código.
"""

from __future__ import annotations

from decimal import Decimal

from core.modelos import Movimiento, Operacion, Politica, Propuesta, Veredicto
from core.puertos import BancoPort, MercadoPort, Reloj

P2 = "Persona 2 (motor): "


def evaluar(
    op: Operacion,
    politica: Politica,
    acumulado_dia_usd: Decimal,
    saldo_usd: Decimal,
) -> Veredicto:
    """Aplica las 6 reglas en orden y devuelve el Veredicto con su motivo."""
    raise NotImplementedError(P2 + "evaluar")


def proponer(
    ingreso: Movimiento,
    banco: BancoPort,
    mercado: MercadoPort,
    reloj: Reloj,
    politica: Politica,
) -> Propuesta:
    """Arma la propuesta completa.

    1) historico = mercado.historico("USD", "COP", 30); rendimiento = banco.rendimiento("USDT")
    2) rutas = motor.rutas.calcular_rutas(...)
    3) elegida = la ruta con más cop_final cuyas operaciones de HOY no queden bloqueadas
    4) veredictos = evaluar() para la reserva de impuestos (USD->USDT) y cada operación
       de la ruta elegida, acumulando el USD del día
    5) ahorro_cop = cop_final(elegida) − cop_final("Todo hoy")
    """
    raise NotImplementedError(P2 + "proponer")
