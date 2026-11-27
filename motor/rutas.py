"""Cálculo de las 3 rutas de conversión (Persona 2). Código 100 % determinista.

Disponible para comparar:
    reserva_impuestos = ingreso × impuestos_pct / 100      (va a USDT, igual en las 3 rutas)
    disponible        = ingreso − reserva_impuestos − colchon_usd
    Las reservas (impuestos y colchón) NO entran en la comparación.

Fórmulas:
    Conversión del día d:  COP = USD × TRM_d × (1 − spread)
    Saldo en USDT:         crece tasa_anual / 365 por día (interés compuesto diario)
    TRM_d:                 historico[d − 1] (el histórico de 30 días simula el mes)

Rutas (nombres EXACTOS, los usa la UI y los fixtures):
    A "Todo hoy":
        convierte todo el disponible el día 1.
    B "Lo justo hoy, el resto rindiendo":
        el día 1 convierte solo lo necesario para cada gasto fijo
        (USD = ceil(monto_cop / (TRM_1 × (1 − spread))), una operación por gasto, categoria = nombre del gasto);
        el resto pasa a USDT (categoria "ahorro") y se convierte a COP en 4 tramos semanales
        (días 8, 15, 22 y 29), cada tramo = saldo_usdt_actual / tramos_restantes, con rendimiento.
    C "Mitad y mitad":
        mitad del disponible el día 1, la otra mitad el día 15 (el USD no rinde).

Ejemplo con los fixtures (Laura): A = 2.605.531,50 · B = 2.612.480,36 · C = 2.608.276,03 COP.
Ver fixtures/propuesta.json.
"""

from __future__ import annotations

from core.modelos import Cotizacion, Movimiento, Politica, Rendimiento, Ruta

P2 = "Persona 2 (motor): "

RUTA_A = "Todo hoy"
RUTA_B = "Lo justo hoy, el resto rindiendo"
RUTA_C = "Mitad y mitad"


def calcular_rutas(
    ingreso: Movimiento,
    historico: list[Cotizacion],
    rendimiento: Rendimiento,
    politica: Politica,
) -> list[Ruta]:
    """Devuelve [A, B, C] con sus operaciones y cop_final (Decimal, 2 decimales)."""
    raise NotImplementedError(P2 + "calcular_rutas")
