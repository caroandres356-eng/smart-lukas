"""Mercado con TRM real (Persona 1). Cumple core.puertos.MercadoPort.

Lee la TRM histórica de un CSV de datos abiertos (ver banco/datos/README.md).
Si el CSV no existe, usa fixtures/cotizaciones_30d.json (valores sintéticos).
Las cotizaciones van SIN spread en `tasa` y con spread=0.01 aparte.
"""

from __future__ import annotations

from pathlib import Path

from core.modelos import Cotizacion, Moneda

P1 = "Persona 1 (banco): "


class MercadoCSV:
    def __init__(self, ruta_csv: str | Path) -> None:
        self.ruta_csv = Path(ruta_csv)

    def historico(self, desde: Moneda, hacia: Moneda, dias: int) -> list[Cotizacion]:
        """Últimas `dias` cotizaciones (de la más antigua a la más reciente).

        - Con CSV: parsear VALOR y VIGENCIADESDE, Decimal, fuente="simulado"
          (los datos son reales pero la operación es simulada).
        - Sin CSV: fallback a fakes.cargar_cotizaciones_ejemplo().
        """
        raise NotImplementedError(P1 + "MercadoCSV.historico")
