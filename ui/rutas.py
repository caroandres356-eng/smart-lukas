"""Pantalla: Rutas. Las 3 formas de convertir lo disponible, cuánto deja cada una y por qué gana la elegida."""

from decimal import Decimal
from html import escape

import streamlit as st

from analisis.escenarios import escenarios, punto_equilibrio
from motor.rutas import RUTA_A
from ui import componentes as c
from ui import estado
from ui.panel import al_cierre
from viz.estilo import CONFIG, LETRAS, color_ruta
from viz.escenarios import grafica_escenarios
from viz.evolucion_echarts import opciones_evolucion
from viz.rutas import grafica_rutas


def _tarjeta_ruta(prop, ruta, todo_hoy) -> str:
    color = color_ruta(ruta.nombre)
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
        dif = prop.ahorro_cop if es_elegida else ruta.cop_final - todo_hoy.cop_final
        frente = f"<b style='color:{'#1f5f24' if es_elegida else '#33403a'}'>{c.pesos_con_signo(dif)}</b> frente a «Todo hoy»"
    nota = f"<div class='d' style='color:#9c2a5a'>{escape(ruta.nota)}</div>" if ruta.nota else ""
    return (
        f"<div class='sl-card{' on' if es_elegida else ''}' style='border-top:4px solid {color}'>"
        f"<div class='top'><div class='k' style='display:flex;align-items:center;gap:8px'>"
        f"<span style='width:10px;height:10px;border-radius:999px;background:{color}'></span>Ruta {LETRAS.get(ruta.nombre, '')}</div>{insignia}</div>"
        f"<div style='font-weight:700;margin-top:6px'>{escape(ruta.nombre)}</div>"
        f"<div class='v'>{c.pesos(ruta.cop_final)}</div>"
        f"<div class='d'>{frente}</div>"
        f"<div class='d'>{escape(ruta.descripcion)} · {len(ruta.operaciones)} operaciones</div>{nota}</div>"
    )


def _escenarios_dolar(prop, pol, historico) -> None:
    """¿Y si el dólar cambia? El usuario elige cuánto se mueve; el motor recalcula las rutas en cada escenario."""
    with st.container(border=True, key="card_rutas_escenarios"):
        c._html("<div class='sl-ct'><h2>¿Y si el dólar cambia durante el mes?</h2>"
                "<p>Mueve el control: el dólar sube o baja poco a poco hasta ese porcentaje el último día. "
                "Lo calcula el mismo motor con un histórico hipotético; es un escenario, no una promesa.</p></div>")
        variacion = st.slider("¿Cuánto se mueve el dólar en el mes?", min_value=0.5, max_value=10.0, value=3.0,
                              step=0.5, format="%.1f %%", key="rutas_variacion_dolar")
        rendimiento = st.session_state["banco"].rendimiento("USDT")
        escs = escenarios(prop.ingreso, historico, rendimiento, pol, Decimal(str(variacion)))
        equilibrio = punto_equilibrio(prop.ingreso, historico, rendimiento, pol, prop.elegida)
        st.plotly_chart(grafica_escenarios(escs, prop.elegida, equilibrio), width="stretch", config=CONFIG)
        letra = LETRAS.get(prop.elegida, "")
        if equilibrio is not None:
            c._html(
                "<div class='sl-stats' style='margin-top:4px'><div class='warn'><div class='n'>"
                f"{str(equilibrio).replace('.', ',')} %</div><div class='t'>punto de equilibrio</div></div>"
                f"<div class='txt'>Si el dólar baja más de {str(equilibrio).replace('.', ',')} % de aquí a fin de mes, "
                f"habría sido mejor convertir todo hoy. Ese es el riesgo de esperar con la ruta {letra}; "
                "a cambio, si el dólar se mantiene o sube, terminas con más pesos.</div></div>"
            )


def render() -> None:
    c.encabezado("Rutas", "Tres formas de convertir lo disponible. El agente elige la que deja más pesos y cubre tus gastos a tiempo.",
                 simulado=estado.fuente_actual() == "simulado")
    prop = estado.propuesta()
    pol = estado.politica()
    historico = st.session_state["mercado"].historico("USD", "COP", 30)
    todo_hoy = next((r for r in prop.rutas if r.nombre == RUTA_A), None)

    cols = st.columns(len(prop.rutas), gap="medium")
    for col, ruta in zip(cols, prop.rutas):
        with col:
            c._html(_tarjeta_ruta(prop, ruta, todo_hoy))

    with st.container(border=True, key="card_rutas_evol"):
        c._html("<div class='sl-ct'><h2>Cómo se acumulan los pesos en cada ruta</h2>"
                "<p>Pasa el mouse para ver cuánto lleva cada ruta cada día. La línea punteada es lo mínimo para tus gastos fijos.</p></div>")
        graf, cierre = st.columns([3, 1], gap="small")
        with graf:
            c.echarts(opciones_evolucion(prop, historico, pol), alto=380, clave="rutas_evol")
        with cierre:
            c._html(al_cierre(prop))

    with st.container(border=True, key="card_rutas_comp"):
        st.plotly_chart(grafica_rutas(prop), width="stretch", config=CONFIG)

    _escenarios_dolar(prop, pol, historico)

    c.seccion("Operaciones de cada ruta")
    for ruta in prop.rutas:
        marca = " ✓ elegida" if ruta.nombre == prop.elegida else ""
        with st.expander(f"Ruta {LETRAS.get(ruta.nombre, '')} · {ruta.nombre}{marca}", expanded=ruta.nombre == prop.elegida):
            st.dataframe(
                [
                    {"Fecha": c.fecha_corta(o.fecha_programada), "Operación": c.monto_op(o), "Para": o.categoria.capitalize()}
                    for o in ruta.operaciones
                ],
                hide_index=True,
                width="stretch",
            )
