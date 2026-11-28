"""Escenarios del dólar: ¿la ruta elegida sigue ganando si el dólar sube o baja durante el mes?

Aquí NO se calculan pesos. Solo se arma un histórico hipotético (la TRM del mes movida poco a poco
hasta ±X % el último día) y se le pasa a la MISMA función del motor: motor.rutas.calcular_rutas.
El día del pago (día 1) no cambia: el dólar de hoy ya se conoce; lo incierto es el resto del mes.
Todo esto es un ESCENARIO, nunca una promesa.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from core.modelos import Cotizacion, Movimiento, Politica, Rendimiento, Ruta
from motor.rutas import DIAS_PERIODO, RUTA_A, calcular_rutas

CENTAVO = Decimal("0.01")


def historico_escenario(historico: list[Cotizacion], variacion_pct: Decimal) -> list[Cotizacion]:
    """La TRM del mes multiplicada por una rampa que va de 0 % (día 1) a variacion_pct % (último día)."""
    periodo = historico[:DIAS_PERIODO]
    ultimo = len(periodo) - 1 or 1
    salida = []
    for i, cot in enumerate(periodo):
        factor = 1 + Decimal(variacion_pct) / 100 * Decimal(i) / Decimal(ultimo)
        salida.append(cot.model_copy(update={"tasa": (cot.tasa * factor).quantize(CENTAVO, rounding=ROUND_HALF_UP)}))
    return salida


@dataclass(frozen=True)
class Escenario:
    nombre: str  # "baja", "igual", "sube"
    titulo: str  # "El dólar baja 3 %"
    variacion_pct: Decimal
    rutas: list[Ruta]  # resultado del motor para ese escenario

    def ruta(self, nombre: str) -> Ruta:
        return next(r for r in self.rutas if r.nombre == nombre)

    def ganadora(self) -> Ruta:
        """La que el motor elegiría: la VÁLIDA con más pesos (si ninguna es válida, «Todo hoy»)."""
        validas = [r for r in self.rutas if r.valida]
        return max(validas, key=lambda r: r.cop_final) if validas else self.ruta(RUTA_A)


def _texto_pct(v: Decimal) -> str:
    return f"{v.normalize():f}".replace(".", ",")


def escenarios(
    ingreso: Movimiento,
    historico: list[Cotizacion],
    rendimiento: Rendimiento,
    politica: Politica,
    variacion_pct: Decimal,
) -> list[Escenario]:
    """[baja, igual, sube] con las rutas que calcula el motor en cada uno."""
    v = abs(Decimal(variacion_pct))
    casos = [
        ("baja", f"El dólar baja {_texto_pct(v)} %", -v),
        ("igual", "El dólar se mantiene", Decimal(0)),
        ("sube", f"El dólar sube {_texto_pct(v)} %", v),
    ]
    return [
        Escenario(nombre, titulo, pct, calcular_rutas(ingreso, historico_escenario(historico, pct), rendimiento, politica))
        for nombre, titulo, pct in casos
    ]


def punto_equilibrio(
    ingreso: Movimiento,
    historico: list[Cotizacion],
    rendimiento: Rendimiento,
    politica: Politica,
    ruta: str,
    maximo_pct: Decimal = Decimal("20"),
) -> Decimal | None:
    """Cuánto tendría que BAJAR el dólar en el mes (en %) para que «Todo hoy» deje tantos pesos como `ruta`.

    Busca por bisección llamando al motor en cada paso. None si `ruta` ya pierde hoy o si sigue ganando
    aunque el dólar baje `maximo_pct` %.
    """

    def ventaja(bajada: Decimal) -> Decimal:
        rutas = {r.nombre: r for r in calcular_rutas(ingreso, historico_escenario(historico, -bajada), rendimiento, politica)}
        return rutas[ruta].cop_final - rutas[RUTA_A].cop_final

    if ruta == RUTA_A or ventaja(Decimal(0)) <= 0 or ventaja(maximo_pct) > 0:
        return None
    bajo, alto = Decimal(0), Decimal(maximo_pct)
    while alto - bajo > Decimal("0.005"):
        medio = (bajo + alto) / 2
        if ventaja(medio) > 0:
            bajo = medio
        else:
            alto = medio
    return alto.quantize(CENTAVO, rounding=ROUND_HALF_UP)
