"""Gráfica · Escenarios del dólar: pesos de más (o de menos) de cada ruta frente a «Todo hoy».

Recibe los escenarios ya calculados por el motor (analisis.escenarios) y solo los dibuja.
Barras agrupadas por escenario con línea de cero = «Todo hoy». Lo que va por debajo de cero
es una ruta que perdería frente a convertir todo el día del pago. Siempre rotulado como ESCENARIO.
"""

from __future__ import annotations

from decimal import Decimal

import plotly.graph_objects as go

from analisis.escenarios import Escenario
from motor.rutas import RUTA_A
from viz import estilo


def _marcas(bajo: float, alto: float) -> list[int]:
    """Marcas redondas del eje (5.000, 10.000, 20.000…) que incluyen el cero."""
    rango = alto - bajo
    paso = next((p for p in (1_000, 2_000, 5_000, 10_000, 20_000, 50_000, 100_000) if rango / p <= 6), 200_000)
    inicio = int(bajo // paso) * paso
    return [v for v in range(inicio, int(alto) + paso, paso) if bajo <= v <= alto]


def grafica_escenarios(escenarios: list[Escenario], elegida: str, equilibrio: Decimal | None) -> go.Figure:
    x = [e.titulo for e in escenarios]
    nombres = [r.nombre for r in escenarios[0].rutas if r.nombre != RUTA_A]
    fig = go.Figure()
    for nombre in nombres:
        difs, textos, tooltips, rayas = [], [], [], []
        for e in escenarios:
            ruta, base = e.ruta(nombre), e.ruta(RUTA_A)
            dif = ruta.cop_final - base.cop_final
            difs.append(float(dif))
            textos.append(estilo.pesos_con_signo(dif))
            rayas.append("" if ruta.valida else "/")
            tooltips.append(
                f"<b>{e.titulo}</b><br>{estilo.nombre_corto(nombre)}: {estilo.pesos(ruta.cop_final)}"
                f"<br>«Todo hoy»: {estilo.pesos(base.cop_final)}<br>Diferencia: {estilo.pesos_con_signo(dif)}"
                + (f"<br>{ruta.nota}" if ruta.nota else "")
            )
        es_elegida = nombre == elegida
        nunca_valida = all(r == "/" for r in rayas)
        fig.add_trace(go.Bar(
            name=estilo.nombre_corto(nombre) + (" (no cubre tus gastos)" if nunca_valida else ""),
            x=x, y=difs,
            # Rayas blancas ENCIMA del color de la ruta ("overlay") para las que no cubren los gastos.
            marker=dict(color=estilo.color_ruta(nombre), line=dict(width=0),
                        pattern=dict(shape=rayas, fillmode="overlay", fgcolor=estilo.TINTA_CLARA, fgopacity=0.55, size=7)),
            text=textos, textposition="outside", cliponaxis=False, constraintext="none",
            textfont=dict(size=12, color=estilo.TINTA),
            hovertext=tooltips, hoverinfo="text",
        ))

    # Quién gana en cada escenario (lo que elegiría el motor), arriba de cada grupo.
    for e in escenarios:
        gana = e.ganadora()
        fig.add_annotation(
            x=e.titulo, y=1.02, yref="paper", yanchor="bottom", showarrow=False,
            text=f"Gana <b>{estilo.LETRAS.get(gana.nombre, '')} · {gana.nombre}</b>",
            font=dict(size=12, color="#1f5f24" if gana.nombre == elegida else "#7a4a00"),
            bgcolor="#f1f8f2" if gana.nombre == elegida else "#fff4df", borderpad=4,
        )

    letra = estilo.LETRAS.get(elegida, "")
    if equilibrio is not None:
        titulo = f"Si el dólar baja más de {str(equilibrio).replace('.', ',')} % en el mes, convertir todo hoy le gana a la ruta {letra}"
    else:
        titulo = f"La ruta {letra} sigue ganando aunque el dólar se mueva"
    subtitulo = "Pesos de más (o de menos) frente a «Todo hoy» · Escenario hipotético, no es una promesa"
    estilo.aplicar(fig, titulo, subtitulo, alto=420)

    valores = [float(v) for t in fig.data for v in t.y]
    margen = (max(valores) - min(min(valores), 0)) * 0.22 or 1000
    bajo, alto = min(min(valores), 0) - margen, max(max(valores), 0) + margen
    marcas = _marcas(bajo, alto)
    fig.update_layout(
        barmode="group", bargap=0.35, bargroupgap=0.12, showlegend=True,
        legend=dict(orientation="h", x=0, xanchor="left", y=-0.14, yanchor="top", font=dict(size=12)),
        margin=dict(t=120, b=80),
    )
    fig.update_yaxes(tickvals=marcas, ticktext=[estilo.pesos_con_signo(Decimal(m)) for m in marcas],
                     zeroline=True, zerolinecolor=estilo.TINTA_2, zerolinewidth=1.5, range=[bajo, alto],
                     title=dict(text="COP frente a «Todo hoy»", font=dict(size=12, color=estilo.TEXTO_SECUNDARIO)))
    fig.update_xaxes(tickfont=dict(size=13, color=estilo.TINTA))
    fig.add_annotation(xref="paper", x=1, y=0, yshift=-2, yanchor="top", xanchor="right", showarrow=False,
                       text="línea en $0 = «Todo hoy»", font=dict(size=11, color=estilo.TEXTO_SECUNDARIO))
    return fig
