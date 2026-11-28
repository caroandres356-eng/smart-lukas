"""Pantalla 6: Cierre del mes (transparencia: qué hizo, por qué y con cuánta plata)."""

import streamlit as st

from motor.rutas import RUTA_A
from ui import componentes as c
from ui import estado
from viz.estilo import CONFIG
from viz.evolucion import grafica_evolucion


def render() -> None:
    c.encabezado("Cierre del mes", "Qué hizo el agente, por qué y cuánta plata te dejó.",
                 simulado=estado.fuente_actual() == "simulado")
    prop = estado.propuesta()

    c.cifra_principal(
        "Ahorraste",
        c.pesos(prop.ahorro_cop),
        "frente a convertir todo el día 1",
        positiva=prop.ahorro_cop > 0,
    )

    elegida = prop.ruta_elegida()
    todo_hoy = next((r for r in prop.rutas if r.nombre == RUTA_A), None)
    c1, c2 = st.columns(2)
    with c1:
        c.tarjeta(f"Con «{elegida.nombre}»", c.pesos(elegida.cop_final), "La ruta que eligió el agente",
                  resaltada=True, insignia=c.pill("✓ Elegida", "ok"))
    if todo_hoy:
        with c2:
            c.tarjeta("Con «Todo hoy»", c.pesos(todo_hoy.cop_final), "Lo que habrías tenido convirtiendo todo el día 1")

    from motor.explicador import explicar

    texto = estado.intentar(explicar, prop)
    c.seccion("En palabras simples")
    c.cita(texto or "La explicación la genera motor/explicador.py.")

    historico = st.session_state["mercado"].historico("USD", "COP", 30)
    with st.container(border=True):
        st.plotly_chart(grafica_evolucion(prop, historico, estado.politica()), width="stretch", config=CONFIG)
