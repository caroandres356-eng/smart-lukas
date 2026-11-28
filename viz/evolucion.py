"""Gráfica 3 · Evolución de los pesos durante el mes, por ruta.

Cada punto son los pesos ya convertidos hasta ese día. No es un cálculo nuevo: suma las operaciones
que armó el motor (`Ruta.operaciones`) con la misma tasa del motor (`motor.rutas.tasa_neta`), día por día.
El último punto de cada ruta coincide con su `cop_final` (lo verifica tests/test_viz.py).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import plotly.graph_objects as go

from core.modelos import Cotizacion, Politica, Propuesta, Ruta
from motor.rutas import DIAS_PERIODO, RUTA_A, RUTA_B, RUTA_C, cop, fecha_del_gasto, tasa_neta
from viz import estilo

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre")


def serie_pesos(ruta: Ruta, historico: list[Cotizacion]) -> list[tuple[date, Decimal]]:
    """[(fecha, COP acumulados hasta esa fecha)] para los 30 días del periodo."""
    periodo = historico[:DIAS_PERIODO]
    tasas = {c.fecha: tasa_neta(c) for c in periodo}
    serie, acumulado = [], Decimal(0)
    hacia_cop = sorted((o for o in ruta.operaciones if o.hacia == "COP"), key=lambda o: o.fecha_programada)
    i = 0
    for cot in periodo:
        while i < len(hacia_cop) and hacia_cop[i].fecha_programada <= cot.fecha:
            acumulado += hacia_cop[i].monto * tasas[hacia_cop[i].fecha_programada]
            i += 1
        serie.append((cot.fecha, cop(acumulado)))
    return serie


def _color(nombre: str, es_elegida: bool) -> str:
    if es_elegida:
        return estilo.VERDE
    return {RUTA_A: estilo.GRIS_A, RUTA_C: estilo.GRIS_C}.get(nombre, estilo.GRIS)


def grafica_evolucion(propuesta: Propuesta, historico: list[Cotizacion], politica: Politica | None = None) -> go.Figure:
    dia0 = historico[0].fecha
    fig = go.Figure()

    # Las no elegidas primero (quedan detrás); la elegida al final, encima.
    rutas = sorted(propuesta.rutas, key=lambda r: r.nombre == propuesta.elegida)
    for ruta in rutas:
        es_elegida = ruta.nombre == propuesta.elegida
        serie = serie_pesos(ruta, historico)
        fechas = [f for f, _ in serie]
        valores = [float(v) for _, v in serie]
        dias = [(f - dia0).days + 1 for f in fechas]  # día 1 = día del pago
        fig.add_trace(
            go.Scatter(
                x=fechas,
                y=valores,
                name=estilo.nombre_corto(ruta.nombre),
                mode="lines",
                line=dict(color=_color(ruta.nombre, es_elegida), width=3 if es_elegida else 2, shape="hv"),
                opacity=1 if es_elegida else 0.85,
                customdata=[[estilo.pesos(v), d] for (_, v), d in zip(serie, dias)],
                hovertemplate="%{customdata[0]}<extra>" + estilo.nombre_corto(ruta.nombre) + "</extra>",
            )
        )
        if not es_elegida:
            # Las rutas grises se nombran al inicio, donde sus líneas están separadas (al final se juntan).
            fig.add_annotation(
                x=fechas[0], y=valores[0], text=estilo.nombre_corto(ruta.nombre), showarrow=False,
                xanchor="left", yanchor="bottom", yshift=3, font=dict(size=11, color=estilo.TEXTO_SECUNDARIO),
            )
        if es_elegida:
            # Puntos en los días en que la ruta elegida convierte a pesos.
            dias_conversion = sorted({o.fecha_programada for o in ruta.operaciones if o.hacia == "COP"})
            puntos = [(f, v) for f, v in serie if f in dias_conversion]
            fig.add_trace(
                go.Scatter(
                    x=[f for f, _ in puntos],
                    y=[float(v) for _, v in puntos],
                    mode="markers",
                    marker=dict(size=10, color=estilo.VERDE, line=dict(width=2, color=estilo.TINTA_CLARA)),
                    showlegend=False,
                    hoverinfo="skip",
                )
            )
            fecha_fin, valor_fin = serie[-1]
            fig.add_annotation(
                x=fecha_fin, y=float(valor_fin), text=f"<b>{estilo.pesos(valor_fin)}</b>",
                showarrow=False, xanchor="right", yanchor="bottom", yshift=6, font=dict(size=13),
            )

    # Contexto: los días en que hay que pagar gastos fijos.
    if politica:
        for gasto in politica.gastos_fijos:
            fecha = fecha_del_gasto(gasto, dia0)
            if dia0 <= fecha <= historico[min(len(historico), DIAS_PERIODO) - 1].fecha:
                fig.add_vline(x=fecha, line=dict(color=estilo.EJE, width=1))
                fig.add_annotation(
                    x=fecha, y=0, yref="paper", text=f"{gasto.nombre.capitalize()} (día {gasto.dia})",
                    showarrow=False, xanchor="left", yanchor="bottom", xshift=4,
                    font=dict(size=11, color=estilo.TEXTO_SECUNDARIO),
                )

    if propuesta.elegida == RUTA_B:
        titulo = "La ruta B convierte lo justo al inicio y termina con más pesos"
        subtitulo = "Pesos convertidos acumulados por día · el resto rinde en USDT y sale en 4 tramos semanales"
    else:
        titulo = f"Así se acumulan los pesos con «{propuesta.elegida}»"
        subtitulo = "Pesos convertidos acumulados por día, por ruta"

    estilo.aplicar(fig, titulo, subtitulo, alto=400)
    maximo = max(max(t.y) for t in fig.data if t.y)
    fig.update_layout(
        showlegend=True,
        legend=dict(orientation="h", x=0, xanchor="left", y=-0.2, yanchor="top", font=dict(size=12),
                    traceorder="reversed"),
        hovermode="x unified",
        margin=dict(b=96),
    )
    fig.update_xaxes(tickformat="%-d", hoverformat="Día %-d", dtick=86400000 * 7, tick0=dia0,
                     title=dict(text=f"Día de {MESES[dia0.month - 1]} {dia0.year}",
                                font=dict(size=12, color=estilo.TEXTO_SECUNDARIO)),
                     showspikes=True, spikemode="across", spikethickness=1,
                     spikecolor=estilo.EJE, spikedash="solid")
    marcas, textos = estilo.eje_pesos(maximo * 1.1)
    fig.update_yaxes(range=[0, maximo * 1.1], tickvals=marcas, ticktext=textos,
                     title=dict(text="COP acumulados", font=dict(size=12, color=estilo.TEXTO_SECUNDARIO)))
    return fig
