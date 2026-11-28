"""Gráfica 1 · Las 3 rutas y el ahorro frente a «Todo hoy».

Por qué barras de DIFERENCIA y no de pesos finales: las 3 rutas dejan ~2,6 millones y se separan por
unos pocos miles. Barras de 0 a 2,6 M se verían iguales, y recortar el eje exageraría la diferencia.
Mostrar "cuánto más que Todo hoy" empieza honestamente en 0 y cuenta justo la historia de la demo.
Los pesos finales de cada ruta van en el tooltip y en el subtítulo.
"""

from __future__ import annotations

import plotly.graph_objects as go

from core.modelos import Propuesta
from motor.rutas import RUTA_A
from viz import estilo


def grafica_rutas(propuesta: Propuesta) -> go.Figure:
    todo_hoy = next(r for r in propuesta.rutas if r.nombre == RUTA_A)
    elegida = propuesta.ruta_elegida()

    nombres, diferencias, colores, etiquetas, tooltips = [], [], [], [], []
    for ruta in propuesta.rutas:  # orden fijo A, B, C: el color sigue a la ruta, no a su puesto
        es_elegida = ruta.nombre == propuesta.elegida
        diferencia = propuesta.ahorro_cop if es_elegida else ruta.cop_final - todo_hoy.cop_final
        nombres.append(estilo.nombre_corto(ruta.nombre))
        diferencias.append(float(diferencia))
        colores.append(estilo.VERDE if es_elegida else estilo.GRIS)

        if ruta.nombre == RUTA_A:
            etiqueta = "referencia"
        else:
            etiqueta = estilo.pesos_con_signo(diferencia)
        if es_elegida:
            etiqueta = f"<b>{etiqueta}</b>  ✓ elegida"
        if not ruta.valida:
            etiqueta += "  · no cubre los gastos"
        etiquetas.append(etiqueta)

        tooltip = f"<b>{ruta.nombre}</b><br>Pesos finales: {estilo.pesos(ruta.cop_final)}"
        if ruta.nombre != RUTA_A:
            tooltip += f"<br>Frente a «Todo hoy»: {estilo.pesos_con_signo(diferencia)}"
        if ruta.nota:
            tooltip += f"<br>{ruta.nota}"
        tooltips.append(tooltip)

    fig = go.Figure(
        go.Bar(
            x=diferencias,
            y=nombres,
            orientation="h",
            marker=dict(color=colores, line=dict(width=0)),
            opacity=1,
            text=etiquetas,
            textposition="outside",
            cliponaxis=False,
            hovertext=tooltips,
            hoverinfo="text",
        )
    )
    # Las rutas que no cubren los gastos se ven "apagadas" (relleno con rayas, no solo color).
    fig.update_traces(
        marker_pattern=dict(
            shape=["" if r.valida else "/" for r in propuesta.rutas],
            fgcolor=estilo.TINTA_CLARA,
            fgopacity=0.6,
        )
    )

    maximo = max(max(diferencias), 0.0)
    minimo = min(min(diferencias), 0.0)
    holgura = (maximo - minimo) or 1.0

    if propuesta.ahorro_cop > 0:
        letra = estilo.LETRAS.get(elegida.nombre, "")
        titulo = f"La ruta {letra} te deja {estilo.pesos(propuesta.ahorro_cop)} más que convertir todo hoy"
    else:
        titulo = "Este mes conviene convertir todo hoy"
    subtitulo = f"Terminas con {estilo.pesos(elegida.cop_final)} en vez de {estilo.pesos(todo_hoy.cop_final)}"

    estilo.aplicar(fig, titulo, subtitulo, alto=280)
    fig.update_xaxes(
        range=[minimo - holgura * 0.05, maximo + holgura * 0.75],  # espacio para la etiqueta a la derecha
        tickprefix="$",
        tickformat=",d",  # $2.000 en vez de $2k
        showgrid=True,
        gridcolor=estilo.REJILLA,
        zeroline=True,
        zerolinecolor=estilo.EJE,
        zerolinewidth=1,
        title=dict(text="COP frente a «Todo hoy»", font=dict(size=12, color=estilo.TEXTO_SECUNDARIO)),
    )
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=13))
    return fig
