"""Pantalla 6: Cierre del mes (transparencia: qué hizo, por qué y con cuánta plata)."""

import streamlit as st

from ui import estado


def render() -> None:
    st.title("🧾 Cierre del mes")
    estado.etiqueta_fuente(estado.fuente_actual())
    prop = estado.propuesta()

    st.metric("Ahorro", estado.fmt_cop(prop.ahorro_cop))
    st.success(f"Ahorraste **{estado.fmt_cop(prop.ahorro_cop)} pesos** frente a convertir todo el día 1.")

    from motor.explicador import explicar

    texto = estado.intentar(explicar, prop)
    st.subheader("En palabras simples")
    st.write(texto or "_La explicación la genera motor/explicador.py (Persona 2)._")

    elegida = prop.ruta_elegida()
    todo_hoy = next((r for r in prop.rutas if r.nombre == "Todo hoy"), None)
    c1, c2 = st.columns(2)
    c1.metric(f"Con «{elegida.nombre}»", estado.fmt_cop(elegida.cop_final))
    if todo_hoy:
        c2.metric("Con «Todo hoy»", estado.fmt_cop(todo_hoy.cop_final))
    estado.pendiente_diseno()
