"""Decisor determinista (Persona 2): cada operación sale auto, requiere_aprobacion o bloqueada.

Antes de todo: USD -> USDT es un movimiento interno entre saldos de la persona -> auto
(no cuenta para los límites).

REGLAS, EN ESTE ORDEN (gana la primera que aplique):
    1) Hay una regla aprendida "bloquear" para (tipo, categoria)              -> bloqueada
    2) Hay una regla aprendida "permitir_hasta" para (tipo, categoria)
       y el monto cabe (monto <= monto_max_usd)                              -> auto
    3) La operación sale de USD y deja el saldo USD por debajo de colchon_usd -> bloqueada
    4) monto > auto_max_usd_por_operacion                                    -> requiere_aprobacion
    5) acumulado_dia_usd + monto > auto_max_usd_por_dia                      -> requiere_aprobacion
    6) Si no aplica ninguna                                                  -> auto

El motivo SIEMPRE dice la regla y los números. Montos en USDT cuentan como USD (1:1) para los límites.

La IA NO participa aquí: montos y decisiones son 100 % código.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from core.modelos import CambioPolitica, Movimiento, Operacion, Politica, Propuesta, Veredicto
from core.puertos import BancoPort, MercadoPort, Reloj
from motor.rutas import RUTA_A, calcular_rutas, fmt_usd, operacion_impuestos

DIAS_HISTORICO = 30

_NOMBRE_TIPO = {"conversion": "conversión", "pago": "pago"}


def _regla(politica: Politica, accion: str, op: Operacion) -> CambioPolitica | None:
    for r in politica.reglas_aprendidas:
        if r.accion == accion and r.tipo == op.tipo and r.categoria == op.categoria:
            return r
    return None


def evaluar(
    op: Operacion,
    politica: Politica,
    acumulado_dia_usd: Decimal,
    saldo_usd: Decimal,
) -> Veredicto:
    """Aplica las reglas en orden y devuelve el Veredicto con su motivo."""

    def veredicto(estado: str, motivo: str) -> Veredicto:
        return Veredicto(operacion=op, estado=estado, motivo=motivo)

    monto = op.monto
    que = f"{_NOMBRE_TIPO[op.tipo]} de {op.categoria}"

    if op.desde == "USD" and op.hacia == "USDT":
        return veredicto("auto", "Movimiento interno entre tus saldos; no cuenta para tus límites")

    # 1) Regla aprendida "bloquear"
    if _regla(politica, "bloquear", op):
        return veredicto("bloqueada", f"Regla aprendida: nunca hacer {que}")

    # 2) Regla aprendida "permitir_hasta"
    permitir = _regla(politica, "permitir_hasta", op)
    if permitir and permitir.monto_max_usd is not None and monto <= permitir.monto_max_usd:
        return veredicto(
            "auto",
            f"Regla aprendida: permitir {que} hasta {fmt_usd(permitir.monto_max_usd)} USD "
            f"y esta es de {fmt_usd(monto)} USD",
        )

    # 3) Colchón
    if op.desde == "USD":
        quedaria = saldo_usd - monto
        if quedaria < politica.colchon_usd:
            return veredicto(
                "bloqueada",
                f"Te dejaría {fmt_usd(quedaria)} USD, por debajo de tu colchón de {fmt_usd(politica.colchon_usd)} USD",
            )

    # 4) Límite por operación
    if monto > politica.auto_max_usd_por_operacion:
        return veredicto(
            "requiere_aprobacion",
            f"{fmt_usd(monto)} USD supera tu límite de {fmt_usd(politica.auto_max_usd_por_operacion)} USD por operación",
        )

    # 5) Límite diario
    total_dia = acumulado_dia_usd + monto
    if total_dia > politica.auto_max_usd_por_dia:
        return veredicto(
            "requiere_aprobacion",
            f"Con esta operación hoy llevarías {fmt_usd(total_dia)} USD y tu límite diario es "
            f"{fmt_usd(politica.auto_max_usd_por_dia)} USD",
        )

    # 6) Dentro de los límites
    return veredicto(
        "auto",
        f"Dentro de tus límites: {fmt_usd(monto)} USD de {fmt_usd(politica.auto_max_usd_por_operacion)} USD "
        f"por operación y {fmt_usd(total_dia)} USD de {fmt_usd(politica.auto_max_usd_por_dia)} USD hoy",
    )


def evaluar_en_orden(operaciones: list[Operacion], politica: Politica, saldo_usd_inicial: Decimal) -> list[Veredicto]:
    """Evalúa las operaciones por fecha llevando el acumulado del día y el saldo USD.

    - Acumulado del día: suma de las operaciones hacia COP de ese día que no quedaron bloqueadas.
    - Saldo USD: empieza en el saldo del banco y resta lo que sale de USD y no quedó bloqueado.
    """
    acumulado: dict[date, Decimal] = defaultdict(Decimal)
    saldo = saldo_usd_inicial
    veredictos = []
    for op in sorted(operaciones, key=lambda o: o.fecha_programada):  # sorted es estable
        v = evaluar(op, politica, acumulado[op.fecha_programada], saldo)
        if v.estado != "bloqueada":
            if op.hacia == "COP":
                acumulado[op.fecha_programada] += op.monto
            if op.desde == "USD":
                saldo -= op.monto
        veredictos.append(v)
    return veredictos


def proponer(
    ingreso: Movimiento,
    banco: BancoPort,
    mercado: MercadoPort,
    reloj: Reloj,
    politica: Politica,
) -> Propuesta:
    """Arma la propuesta completa. No ejecuta nada.

    1) Pide el histórico de 30 días, el rendimiento del USDT y los saldos.
    2) Calcula las rutas y elige la VÁLIDA con más cop_final
       (si ninguna es válida, se queda con "Todo hoy", que es la que más convierte de entrada).
    3) Evalúa la reserva de impuestos y las operaciones de la ruta elegida, en orden de fecha.
    4) ahorro_cop = cop_final(elegida) − cop_final("Todo hoy").
    """
    historico = mercado.historico("USD", "COP", DIAS_HISTORICO)
    rendimiento = banco.rendimiento("USDT")
    saldo_usd = sum((s.monto for s in banco.saldos() if s.moneda == "USD"), Decimal(0))

    rutas = calcular_rutas(ingreso, historico, rendimiento, politica)
    todo_hoy = next(r for r in rutas if r.nombre == RUTA_A)
    validas = [r for r in rutas if r.valida]
    elegida = max(validas, key=lambda r: r.cop_final) if validas else todo_hoy

    operaciones = list(elegida.operaciones)
    impuestos = operacion_impuestos(ingreso, politica, reloj.hoy())
    if impuestos:
        operaciones.insert(0, impuestos)

    return Propuesta(
        ingreso=ingreso,
        rutas=rutas,
        elegida=elegida.nombre,
        veredictos=evaluar_en_orden(operaciones, politica, saldo_usd),
        ahorro_cop=elegida.cop_final - todo_hoy.cop_final,
    )
