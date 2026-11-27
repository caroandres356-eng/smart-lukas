"""Backtest (Persona 2): ¿qué ruta habría ganado cada mes con un histórico largo?

Parte el histórico en ventanas consecutivas de 30 días (una por "mes"), y en cada una
llama a calcular_rutas como si el pago llegara el primer día de la ventana.
La ganadora del mes es la ruta VÁLIDA con más cop_final (si ninguna es válida, "Todo hoy").
"""

from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, ConfigDict, Field

from core.modelos import Cotizacion, Movimiento, Politica, Rendimiento
from motor.rutas import DIAS_PERIODO, RUTA_A, RUTA_B, RUTA_C, calcular_rutas

NOMBRES_RUTAS = (RUTA_A, RUTA_B, RUTA_C)


class ResultadoMes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mes: int = Field(ge=1, description="1 = la primera ventana de 30 días.")
    desde: date
    cop_final: dict[str, Decimal] = Field(description="COP finales de cada ruta.")
    validas: dict[str, bool]
    ganadora: str
    ahorro_cop: Decimal = Field(description='cop_final(ganadora) − cop_final("Todo hoy").')


class ResumenBacktest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meses: list[ResultadoMes]
    meses_pedidos: int
    meses_calculados: int
    victorias: dict[str, int] = Field(description="Cuántos meses ganó cada ruta.")
    ahorro_promedio_cop: Decimal = Field(description='Promedio de (ganadora − "Todo hoy") por mes.')
    nota: str | None = None


def backtest(
    ingreso_usd: Decimal,
    historico_largo: list[Cotizacion],
    rendimiento: Rendimiento,
    politica: Politica,
    meses: int = 12,
) -> ResumenBacktest:
    alcanzan = len(historico_largo) // DIAS_PERIODO
    a_calcular = min(meses, alcanzan)

    resultados: list[ResultadoMes] = []
    for i in range(a_calcular):
        ventana = historico_largo[i * DIAS_PERIODO : (i + 1) * DIAS_PERIODO]
        ingreso = Movimiento(fecha=ventana[0].fecha, tipo="ingreso", moneda="USD", monto=Decimal(ingreso_usd))
        rutas = {r.nombre: r for r in calcular_rutas(ingreso, ventana, rendimiento, politica)}
        validas = [r for r in rutas.values() if r.valida]
        ganadora = max(validas, key=lambda r: r.cop_final) if validas else rutas[RUTA_A]
        resultados.append(
            ResultadoMes(
                mes=i + 1,
                desde=ventana[0].fecha,
                cop_final={n: r.cop_final for n, r in rutas.items()},
                validas={n: r.valida for n, r in rutas.items()},
                ganadora=ganadora.nombre,
                ahorro_cop=ganadora.cop_final - rutas[RUTA_A].cop_final,
            )
        )

    conteo = Counter(r.ganadora for r in resultados)
    victorias = {n: conteo.get(n, 0) for n in NOMBRES_RUTAS}
    promedio = (
        (sum((r.ahorro_cop for r in resultados), Decimal(0)) / len(resultados)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        if resultados
        else Decimal(0)
    )

    nota = None
    if a_calcular < meses:
        nota = (
            f"El histórico tiene {len(historico_largo)} días: solo alcanzó para {a_calcular} de {meses} meses "
            f"(cada mes son {DIAS_PERIODO} días)."
        )

    return ResumenBacktest(
        meses=resultados,
        meses_pedidos=meses,
        meses_calculados=a_calcular,
        victorias=victorias,
        ahorro_promedio_cop=promedio,
        nota=nota,
    )
