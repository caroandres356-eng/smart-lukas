"""Gráfica 2 · Reparto del ingreso: impuestos / colchón / disponible para decidir.

Forma: una barra segmentada (un todo partido en sus partes). Los montos salen de
motor.rutas.calcular_reservas; aquí solo se dibujan. Lo que se decide va en verde y las reservas en gris,
porque la historia es "de 1.000 USD, 650 quedan para decidir".
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import plotly.graph_objects as go

from core.modelos import Movimiento, Politica
from motor.rutas import calcular_reservas
from viz import estilo


def _porcentaje(parte: Decimal, total: Decimal) -> str:
    if total <= 0:
        return "0 %"
    return f"{(parte / total * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP)} %"


def grafica_reparto(ingreso: Movimiento, politica: Politica) -> go.Figure:
    reservas = calcular_reservas(ingreso, politica)
    total = ingreso.monto

    partes = [
        ("Impuestos", reservas.impuestos_usd, estilo.GRIS_OSCURO, estilo.TINTA_CLARA, "se guardan en USDT"),
        ("Colchón", reservas.colchon_usd, estilo.GRIS_CLARO, estilo.TINTA_OSCURA, "se queda en USD, nunca se convierte"),
        ("Disponible para decidir", reservas.disponible_usd, estilo.VERDE, estilo.TINTA_CLARA, "lo que comparan las 3 rutas"),
    ]

    fig = go.Figure()
    for nombre, monto, color, tinta, detalle in partes:
        if monto <= 0:
            continue  # una parte en cero no dibuja nada
        fig.add_trace(
            go.Bar(
                name=nombre,
                x=[float(monto)],
                y=["ingreso"],
                orientation="h",
                marker=dict(color=color, line=dict(width=0)),
                text=[f"<b>{estilo.dolares(monto)}</b> · {_porcentaje(monto, total)}"],
                textposition="inside",
                insidetextanchor="start",
                textfont=dict(color=tinta, size=13),
                constraintext="none",
                hovertext=[f"<b>{nombre}</b><br>{estilo.dolares(monto)} ({_porcentaje(monto, total)})<br>{detalle}"],
                hoverinfo="text",
            )
        )

    titulo = f"De {estilo.dolares(total)}, {estilo.dolares(reservas.disponible_usd)} quedan para decidir"
    subtitulo = (
        f"Se aparta el {politica.impuestos_pct} % de impuestos y un colchón de "
        f"{estilo.dolares(reservas.colchon_usd)} antes de comparar rutas"
    )
    estilo.aplicar(fig, titulo, subtitulo, alto=210)
    fig.update_layout(
        barmode="stack",
        bargap=0.5,
        showlegend=True,  # 3 partes: la leyenda nombra cada bloque
        legend=dict(orientation="h", x=0, xanchor="left", y=-0.15, yanchor="top", traceorder="normal",
                    font=dict(size=12), itemclick=False, itemdoubleclick=False),
        margin=dict(b=60),
    )
    fig.update_xaxes(visible=False, range=[0, float(total)])
    fig.update_yaxes(visible=False)
    return fig
