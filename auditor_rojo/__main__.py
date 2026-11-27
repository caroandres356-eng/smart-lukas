"""Punto de entrada de CLI: ``python -m auditor_rojo``.

Corre 100 escenarios adversarios contra `ObjetivoSimuladoDefensivo` e imprime
el reporte en Markdown (por defecto) o JSON (con ``--json``).

Uso::

    python -m auditor_rojo
    python -m auditor_rojo --json
    python -m auditor_rojo --cantidad 50
    python -m auditor_rojo --json --cantidad 20
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal

from auditor_rojo.corredor import CorredorAuditorRojo, ObjetivoSimuladoDefensivo
from auditor_rojo.reporte import renderizar_markdown


def _parsear_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="auditor_rojo",
        description="El Auditor Rojo — suite de tortura adversaria para agentes bancarios.",
    )
    parser.add_argument(
        "--json",
        dest="formato_json",
        action="store_true",
        default=False,
        help="Emite la salida como JSON en lugar de Markdown.",
    )
    parser.add_argument(
        "--cantidad",
        type=int,
        default=100,
        metavar="N",
        help="Número de escenarios a ejecutar (por defecto: 100).",
    )
    return parser.parse_args(argv)


def _decimal_a_str(obj: object) -> object:
    """Serializa `Decimal` a cadena para `json.dumps`."""
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Objeto no serializable: {type(obj)!r}")


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada principal. Devuelve el código de salida."""
    args = _parsear_args(argv)

    objetivo = ObjetivoSimuladoDefensivo()
    corredor = CorredorAuditorRojo(objetivo)

    reporte = corredor.correr(cantidad=args.cantidad)

    if args.formato_json:
        datos = reporte.model_dump(mode="python")
        print(json.dumps(datos, default=_decimal_a_str, ensure_ascii=False, indent=2))
    else:
        print(renderizar_markdown(reporte))

    # Código de salida: 0 si todos los escenarios pasaron, 1 si hubo fallos.
    return 0 if reporte.fallados == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
