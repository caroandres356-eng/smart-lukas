"""Funciones puras para construir y renderizar reportes de El Auditor Rojo."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from auditor_rojo.puertos import ReporteAuditoria, ResultadoEscenario

_CUATRO_DECIMALES = Decimal("0.0001")


def construir_reporte(resultados: Sequence[ResultadoEscenario]) -> ReporteAuditoria:
    """Construye un `ReporteAuditoria` agregado a partir de resultados individuales."""
    lista = list(resultados)
    total = len(lista)
    pasados = sum(1 for r in lista if r.paso)
    fallados = total - pasados
    tasa_exito = (
        Decimal("0.0000")
        if total == 0
        else (Decimal(pasados) / Decimal(total)).quantize(_CUATRO_DECIMALES)
    )

    por_categoria: dict[str, dict[str, int]] = {}
    for res in lista:
        cubeta = por_categoria.setdefault(
            res.categoria, {"total": 0, "pasados": 0, "fallados": 0}
        )
        cubeta["total"] += 1
        if res.paso:
            cubeta["pasados"] += 1
        else:
            cubeta["fallados"] += 1

    return ReporteAuditoria(
        total=total,
        pasados=pasados,
        fallados=fallados,
        tasa_exito=tasa_exito,
        por_categoria=por_categoria,
        resultados=lista,
    )


def renderizar_markdown(reporte: ReporteAuditoria) -> str:
    """Renderiza un `ReporteAuditoria` como documento Markdown legible."""
    porcentaje = (reporte.tasa_exito * Decimal("100")).quantize(Decimal("0.01"))
    lineas = [
        "# Reporte de Auditoría — El Auditor Rojo",
        "",
        "## Resumen",
        "",
        f"- **Total escenarios:** {reporte.total}",
        f"- **Pasados:** {reporte.pasados}",
        f"- **Fallados:** {reporte.fallados}",
        f"- **Tasa de éxito:** {porcentaje}% (`{reporte.tasa_exito}`)",
        "",
        "## Resultados por categoría",
        "",
        "| Categoría | Total | Pasados | Fallados |",
        "| --- | ---: | ---: | ---: |",
    ]

    for categoria, conteos in reporte.por_categoria.items():
        lineas.append(
            f"| `{categoria}` | {conteos['total']} | {conteos['pasados']} | {conteos['fallados']} |"
        )

    if not reporte.por_categoria:
        lineas.append("| _(sin escenarios)_ | 0 | 0 | 0 |")

    fallidos = [r for r in reporte.resultados if not r.paso]
    lineas.extend(["", "## Escenarios fallidos", ""])
    if not fallidos:
        lineas.append("Todos los escenarios pasaron la auditoría.")
    else:
        for r in fallidos:
            lineas.append(
                f"- **{r.escenario_id}** (`{r.categoria}`, bloqueado={r.bloqueado}): {r.motivo}"
            )

    return "\n".join(lineas) + "\n"
