"""Pantalla: Cierre del mes (transparencia: qué hizo el agente, por qué y con cuánta plata)."""

from html import escape

import streamlit as st

from motor.rutas import RUTA_A
from ui import componentes as c
from ui import estado
from ui.panel import ICONO_CHAT, al_cierre
from viz.evolucion import MESES
from viz.evolucion_echarts import opciones_evolucion
from viz.flujo import opciones_flujo


def render() -> None:
    c.encabezado("Cierre del mes", "Qué hizo el agente, por qué y cuánta plata te dejó.",
                 simulado=estado.fuente_actual() == "simulado")
    prop = estado.propuesta()
    pol = estado.politica()
    historico = st.session_state["mercado"].historico("USD", "COP", 30)
    elegida = prop.ruta_elegida()
    todo_hoy = next((r for r in prop.rutas if r.nombre == RUTA_A), None)
    mes = MESES[prop.ingreso.fecha.month - 1]

    c.cifra_principal(f"En {mes} ganaste", c.pesos_con_signo(prop.ahorro_cop),
                      "frente a convertir todo el día del pago", positiva=prop.ahorro_cop > 0)

    tarjetas = (
        f"<div class='sl-kpi on'><div class='k'>Con «{escape(elegida.nombre)}»<span class='tag'>Elegida</span></div>"
        f"<div class='v'>{c.pesos(elegida.cop_final)}</div><div class='d'>La ruta que eligió el agente</div></div>"
    )
    if todo_hoy:
        tarjetas += (f"<div class='sl-kpi'><div class='k'>Con «Todo hoy»</div><div class='v'>{c.pesos(todo_hoy.cop_final)}</div>"
                     "<div class='d'>Si hubieras convertido todo el día del pago</div></div>")
    c._html(f"<div class='sl-kpis' style='grid-template-columns:repeat(2,minmax(0,1fr))'>{tarjetas}</div>")

    from motor.explicador import explicar

    texto = estado.intentar(explicar, prop)
    if texto:
        c._html(f"<div class='sl-explica' style='margin:0 0 18px'><div class='ic'>{ICONO_CHAT}</div><div style='flex:1;min-width:0'>"
                f"<div class='h'>En palabras simples</div><p>{escape(texto)}</p></div></div>")

    with st.container(border=True, key="card_cierre_evol"):
        c._html(f"<div class='sl-ct'><h2>Tus pesos durante {mes}</h2>"
                "<p>Cómo se fue acumulando cada ruta y lo que dejó cada una al final del mes.</p></div>")
        graf, cierre = st.columns([3, 1], gap="small")
        with graf:
            c.echarts(opciones_evolucion(prop, historico, pol), alto=380, clave="cierre_evol")
        with cierre:
            c._html(al_cierre(prop))

    with st.container(border=True, key="card_cierre_flujo"):
        c._html("<div class='sl-ct'><h2>A dónde fue tu pago</h2><p>Reservas y destinos de la ruta elegida.</p></div>")
        c.echarts(opciones_flujo(prop, pol), alto=340, clave="cierre_flujo")
