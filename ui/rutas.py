"""Pantalla 2: Rutas (comparación A / B / C)."""

from html import escape

import streamlit as st

from motor.rutas import RUTA_A
from ui import componentes as c
from ui import estado
from viz.estilo import CONFIG, LETRAS
from viz.rutas import grafica_rutas


def render() -> None:
    c.encabezado("Rutas", "Tres formas de convertir lo disponible. El agente elige la que deja más pesos y cumple tus reglas.",
                 simulado=estado.fuente_actual() == "simulado")
    prop = estado.propuesta()
    todo_hoy = next((r for r in prop.rutas if r.nombre == RUTA_A), None)

    cols = st.columns(len(prop.rutas))
    for col, ruta in zip(cols, prop.rutas):
        es_elegida = ruta.nombre == prop.elegida
        if es_elegida:
            insignia = c.pill("✓ Elegida", "ok")
        elif not ruta.valida:
            insignia = c.pill("✕ No cubre gastos", "bad")
        else:
            insignia = ""
        if todo_hoy is None or ruta.nombre == RUTA_A:
            frente = "Punto de comparación"
        else:
            diferencia = prop.ahorro_cop if es_elegida else ruta.cop_final - todo_hoy.cop_final
            frente = f"<b>{c.pesos_con_signo(diferencia)}</b> frente a «Todo hoy»"
        detalle = f"{frente}<br>{len(ruta.operaciones)} operaciones · {escape(ruta.descripcion)}"
        if ruta.nota:
            detalle += f"<br><i>{escape(ruta.nota)}</i>"
        with col:
            c.tarjeta(f"Ruta {LETRAS.get(ruta.nombre, '')} · {ruta.nombre}", c.pesos(ruta.cop_final), detalle,
                      resaltada=es_elegida, insignia=insignia)

    with st.container(border=True):
        st.plotly_chart(grafica_rutas(prop), width="stretch", config=CONFIG)

    c.seccion("Operaciones de cada ruta")
    for ruta in prop.rutas:
        marca = " ✓" if ruta.nombre == prop.elegida else ""
        with st.expander(f"Ruta {LETRAS.get(ruta.nombre, '')} · {ruta.nombre}{marca}", expanded=ruta.nombre == prop.elegida):
            st.dataframe(
                [
                    {"Fecha": c.fecha_corta(o.fecha_programada), "Operación": c.monto_op(o), "Para": o.categoria.capitalize()}
                    for o in ruta.operaciones
                ],
                hide_index=True,
                width="stretch",
            )
