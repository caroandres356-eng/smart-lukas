"""Cálculo de las 3 rutas de conversión (Persona 2). Código 100 % determinista.

Día 0 = fecha del primer elemento del histórico. El periodo es de 30 días (días 0 a 29).

Reservas (iguales en las 3 rutas y FUERA de la comparación):
    impuestos  = ingreso × impuestos_pct / 100   (USD -> USDT el día 0, categoría "impuestos";
                                                  esa operación la agrega decisor.proponer, no las rutas)
    colchón    = colchon_usd                     (se queda en USD, sin operación)
    disponible = ingreso − impuestos − colchón

Fórmulas:
    Conversión del día d:        COP = USD × tasa_d × (1 − spread_d)      (1 USDT = 1 USD)
    USD para un gasto fijo:      monto_cop / (tasa_0 × (1 − spread_0)), redondeado HACIA ARRIBA a centavos
    USDT:                        saldo × (1 + tasa_anual / 365) cada día (interés compuesto diario)
    USD -> USDT:                 sin spread

Rutas (nombres EXACTOS, los usan la UI y los fixtures):
    A "Todo hoy":       día 0, una operación por gasto fijo (categoría = nombre del gasto) + "resto".
    B "Lo justo hoy, el resto rindiendo":
                        día 0, una operación por gasto fijo; el resto pasa a USDT ("rendimiento");
                        4 tramos iguales USDT -> COP los días 7, 14, 21 y 28 ("escalonado");
                        el último tramo incluye todo el interés generado.
    C "Mitad y mitad":  50 % del disponible el día 0 y 50 % el día 14 ("mitad").

Una ruta es VÁLIDA solo si, para cada gasto fijo, los COP ya convertidos hasta la fecha del gasto
(acumulado, incluyendo conversiones de ese mismo día) alcanzan para pagar ese gasto y los anteriores.

Redondeo: USD a 2 decimales, COP a 0 decimales (ROUND_HALF_UP).
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP, Decimal

from core.modelos import Cotizacion, GastoFijo, Movimiento, Operacion, Politica, Rendimiento, Ruta

RUTA_A = "Todo hoy"
RUTA_B = "Lo justo hoy, el resto rindiendo"
RUTA_C = "Mitad y mitad"

DIAS_PERIODO = 30
DIAS_TRAMOS = (7, 14, 21, 28)
DIA_MITAD = 14

CENTAVO = Decimal("0.01")
PESO = Decimal("1")


# --------------------------------------------------------------------------- utilidades


def usd(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def usd_hacia_arriba(valor: Decimal) -> Decimal:
    return valor.quantize(CENTAVO, rounding=ROUND_CEILING)


def cop(valor: Decimal) -> Decimal:
    return valor.quantize(PESO, rounding=ROUND_HALF_UP)


def fmt_miles(valor: Decimal, decimales: int = 0) -> str:
    """1800000 -> '1.800.000'; 454.55 -> '454,55' (formato colombiano). Sin decimales si es entero."""
    valor = Decimal(valor)
    if decimales and valor != valor.to_integral_value():
        texto = f"{valor.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP):,.{decimales}f}"
    else:
        texto = f"{valor.quantize(PESO, rounding=ROUND_HALF_UP):,.0f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def fmt_usd(valor: Decimal) -> str:
    return fmt_miles(valor, 2)


def fmt_cop(valor: Decimal) -> str:
    return fmt_miles(valor, 0)


@dataclass(frozen=True)
class Reservas:
    impuestos_usd: Decimal
    colchon_usd: Decimal
    disponible_usd: Decimal


def calcular_reservas(ingreso: Movimiento, politica: Politica) -> Reservas:
    """Impuestos y colchón (fuera de la comparación) y lo que queda disponible para las rutas."""
    impuestos = usd(ingreso.monto * politica.impuestos_pct / 100)
    colchon = usd(politica.colchon_usd)
    disponible = max(usd(ingreso.monto - impuestos - colchon), Decimal("0.00"))
    return Reservas(impuestos, colchon, disponible)


def operacion_impuestos(ingreso: Movimiento, politica: Politica, fecha: date) -> Operacion | None:
    """La reserva de impuestos: USD -> USDT el día 0, categoría "impuestos"."""
    monto = calcular_reservas(ingreso, politica).impuestos_usd
    if monto <= 0:
        return None
    return Operacion(tipo="conversion", desde="USD", hacia="USDT", monto=monto, categoria="impuestos", fecha_programada=fecha)


def tasa_neta(cot: Cotizacion) -> Decimal:
    """COP que recibes por 1 USD ese día, ya descontado el spread."""
    return cot.tasa * (1 - cot.spread)


def usd_para_gasto(gasto: GastoFijo, cot_dia0: Cotizacion) -> Decimal:
    """USD que hay que convertir el día 0 para cubrir el gasto (redondeado hacia arriba)."""
    return usd_hacia_arriba(gasto.monto_cop / tasa_neta(cot_dia0))


def fecha_del_gasto(gasto: GastoFijo, dia0: date) -> date:
    """Próxima fecha (desde el día 0, inclusive) con ese día del mes. Si el mes no tiene ese día, usa el último."""
    anio, mes = dia0.year, dia0.month
    if gasto.dia < dia0.day:
        anio, mes = (anio + 1, 1) if mes == 12 else (anio, mes + 1)
    return date(anio, mes, min(gasto.dia, calendar.monthrange(anio, mes)[1]))


# --------------------------------------------------------------------------- rutas


def _conversion(desde: str, hacia: str, monto: Decimal, categoria: str, fecha: date) -> Operacion:
    return Operacion(tipo="conversion", desde=desde, hacia=hacia, monto=monto, categoria=categoria, fecha_programada=fecha)


def _ops_gastos(politica: Politica, disponible: Decimal, historico: list[Cotizacion]) -> list[Operacion]:
    """Una conversión USD -> COP el día 0 por cada gasto fijo (sin pasar del disponible)."""
    ops, queda = [], disponible
    dia0 = historico[0]
    for gasto in sorted(politica.gastos_fijos, key=lambda g: fecha_del_gasto(g, dia0.fecha)):
        monto = min(usd_para_gasto(gasto, dia0), queda)
        if monto > 0:
            ops.append(_conversion("USD", "COP", monto, gasto.nombre, dia0.fecha))
            queda -= monto
    return ops


def _ruta_a(disponible: Decimal, historico: list[Cotizacion], politica: Politica) -> list[Operacion]:
    ops = _ops_gastos(politica, disponible, historico)
    resto = disponible - sum((o.monto for o in ops), Decimal(0))
    if resto > 0:
        ops.append(_conversion("USD", "COP", resto, "resto", historico[0].fecha))
    return ops


def _ruta_b(disponible: Decimal, historico: list[Cotizacion], politica: Politica, rendimiento: Rendimiento) -> list[Operacion]:
    ops = _ops_gastos(politica, disponible, historico)
    resto = disponible - sum((o.monto for o in ops), Decimal(0))
    if resto <= 0:
        return ops
    ops.append(_conversion("USD", "USDT", resto, "rendimiento", historico[0].fecha))

    factor_diario = 1 + rendimiento.tasa_anual / 365
    tramo_igual = (resto / len(DIAS_TRAMOS)).quantize(CENTAVO, rounding=ROUND_DOWN)
    saldo, dia = resto, 0
    for i, dia_tramo in enumerate(DIAS_TRAMOS):
        while dia < dia_tramo:  # el USDT rinde cada día hasta el tramo
            saldo *= factor_diario
            dia += 1
        ultimo = i == len(DIAS_TRAMOS) - 1
        monto = usd(saldo) if ultimo else tramo_igual  # el último se lleva el interés
        if monto > 0:
            ops.append(_conversion("USDT", "COP", monto, "escalonado", historico[dia_tramo].fecha))
        saldo -= monto
    return ops


def _ruta_c(disponible: Decimal, historico: list[Cotizacion]) -> list[Operacion]:
    mitad = usd(disponible / 2)
    ops = []
    for monto, dia in ((mitad, 0), (disponible - mitad, DIA_MITAD)):
        if monto > 0:
            ops.append(_conversion("USD", "COP", monto, "mitad", historico[dia].fecha))
    return ops


def _cop_por_operacion(op: Operacion, tasas: dict[date, Decimal]) -> Decimal:
    return op.monto * tasas[op.fecha_programada] if op.hacia == "COP" else Decimal(0)


def _validar(ops: list[Operacion], politica: Politica, tasas: dict[date, Decimal], dia0: date) -> str | None:
    """None si la ruta cubre cada gasto fijo a tiempo; si no, la nota que explica por qué."""
    necesario = Decimal(0)
    for gasto in sorted(politica.gastos_fijos, key=lambda g: fecha_del_gasto(g, dia0)):
        fecha = fecha_del_gasto(gasto, dia0)
        necesario += gasto.monto_cop
        convertido = sum((_cop_por_operacion(o, tasas) for o in ops if o.fecha_programada <= fecha), Decimal(0))
        if convertido < necesario:
            falta = cop(necesario - convertido)
            return f"No alcanza para el {gasto.nombre} del día {gasto.dia}: faltan {fmt_cop(falta)} COP"
    return None


def calcular_rutas(
    ingreso: Movimiento,
    historico: list[Cotizacion],
    rendimiento: Rendimiento,
    politica: Politica,
) -> list[Ruta]:
    """Devuelve [A, B, C] con sus operaciones, cop_final (COP enteros), valida y nota."""
    necesarios = max(DIAS_TRAMOS[-1], DIA_MITAD) + 1
    if len(historico) < necesarios:
        raise ValueError(f"Se necesitan al menos {necesarios} días de histórico y llegaron {len(historico)}.")
    historico = historico[:DIAS_PERIODO]
    dia0 = historico[0].fecha
    tasas = {c.fecha: tasa_neta(c) for c in historico}
    disponible = calcular_reservas(ingreso, politica).disponible_usd

    definiciones = [
        (RUTA_A, "Convierte todo lo disponible hoy.", _ruta_a(disponible, historico, politica)),
        (
            RUTA_B,
            "Convierte hoy solo lo de los gastos fijos; el resto queda en USDT rindiendo y se convierte en 4 tramos semanales.",
            _ruta_b(disponible, historico, politica, rendimiento),
        ),
        (RUTA_C, "Convierte la mitad hoy y la otra mitad en 14 días.", _ruta_c(disponible, historico)),
    ]

    rutas = []
    for nombre, descripcion, ops in definiciones:
        cop_final = cop(sum((_cop_por_operacion(o, tasas) for o in ops), Decimal(0)))
        nota = _validar(ops, politica, tasas, dia0)
        rutas.append(Ruta(nombre=nombre, descripcion=descripcion, operaciones=ops, cop_final=cop_final, valida=nota is None, nota=nota))
    return rutas
