"""Pantalla 3: Operaciones con su veredicto (auto / requiere aprobación / bloqueada)."""

import streamlit as st

from ui import estado

ICONOS = {"auto": "🟢 auto", "requiere_aprobacion": "🟡 requiere aprobación", "bloqueada": "🔴 bloqueada"}


def render() -> None:
    st.title("⚙️ Operaciones")
    estado.etiqueta_fuente(estado.fuente_actual())
    prop = estado.propuesta()

    st.subheader(f"Ruta elegida: {prop.elegida}")
    st.dataframe(
        [
            {
                "Estado": ICONOS[v.estado],
                "Fecha": v.operacion.fecha_programada,
                "De→A": f"{v.operacion.desde}→{v.operacion.hacia}",
                "Monto": f"{v.operacion.monto}",
                "Categoría": v.operacion.categoria,
                "Motivo": v.motivo,
            }
            for v in prop.veredictos
        ],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Movimientos del banco")
    st.dataframe(
        [m.model_dump(mode="json") for m in st.session_state["banco"].movimientos()],
        hide_index=True,
        width="stretch",
    )
    estado.pendiente_diseno()
