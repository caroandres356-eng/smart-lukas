"""Pantalla 2: Rutas (comparación A / B / C)."""

import plotly.graph_objects as go
import streamlit as st

from ui import estado


def render() -> None:
    st.title("🧭 Rutas")
    estado.etiqueta_fuente(estado.fuente_actual())
    prop = estado.propuesta()

    st.dataframe(
        [
            {
                "Ruta": r.nombre + (" ✅" if r.nombre == prop.elegida else ""),
                "Pesos finales": estado.fmt_cop(r.cop_final),
                "Operaciones": len(r.operaciones),
                "Descripción": r.descripcion,
            }
            for r in prop.rutas
        ],
        hide_index=True,
        width="stretch",
    )

    fig = go.Figure(
        go.Bar(
            x=[r.nombre for r in prop.rutas],
            y=[float(r.cop_final) for r in prop.rutas],
            marker_color=["#2e7d32" if r.nombre == prop.elegida else "#9e9e9e" for r in prop.rutas],
            text=[estado.fmt_cop(r.cop_final) for r in prop.rutas],
            textposition="outside",
        )
    )
    minimo = min(float(r.cop_final) for r in prop.rutas)
    fig.update_layout(yaxis_title="COP", yaxis_range=[minimo * 0.995, None], height=360, margin=dict(t=20))
    st.plotly_chart(fig, width="stretch")

    st.metric("Elegida", prop.elegida, delta=f"{estado.fmt_cop(prop.ahorro_cop)} vs. Todo hoy")

    for r in prop.rutas:
        with st.expander(f"Operaciones de «{r.nombre}»"):
            st.dataframe(
                [
                    {"Fecha": o.fecha_programada, "Tipo": o.tipo, "De→A": f"{o.desde}→{o.hacia}",
                     "Monto": f"{o.monto}", "Categoría": o.categoria}
                    for o in r.operaciones
                ],
                hide_index=True,
                width="stretch",
            )
    estado.pendiente_diseno()
