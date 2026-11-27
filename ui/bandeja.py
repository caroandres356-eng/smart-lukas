"""Pantalla 4: Bandeja de aprobaciones (control humano)."""

import streamlit as st

from ui import estado

RESPUESTAS = {"solo_esta_vez": "Solo esta vez", "siempre": "Siempre en este rango", "nunca": "Nunca"}


def _responder(solicitud_id: str, respuesta: str) -> None:
    from motor.politica import aplicar_cambio

    cambio = estado.intentar(st.session_state["bandeja"].responder, solicitud_id, respuesta)
    if cambio is not None:
        st.session_state["politica"] = estado.intentar(
            aplicar_cambio, st.session_state["politica"], cambio, respaldo=lambda: st.session_state["politica"]
        )


def render() -> None:
    st.title("📥 Bandeja")
    reloj = st.session_state["reloj"]
    pol = estado.politica()
    estado.intentar(st.session_state["bandeja"].actualizar_vencidas)
    solicitudes = estado.solicitudes()

    st.caption(
        f"Hora (UTC): {reloj.ahora():%H:%M:%S} · Las solicitudes vencen en {pol.vence_en_segundos} s · "
        f"Máximo {pol.max_interrupciones_dia} interrupciones al día"
    )

    pendientes = [s for s in solicitudes if s.estado == "pendiente"]
    st.subheader(f"Pendientes ({len(pendientes)})")
    for sol in pendientes:
        quedan = int((sol.vence - reloj.ahora()).total_seconds())
        with st.container(border=True):
            op = sol.operacion
            st.markdown(f"**{op.monto} {op.desde} → {op.hacia}** · {op.categoria} · ⏳ {max(quedan, 0)} s")
            st.caption(sol.motivo)
            cols = st.columns(3)
            for col, (clave, texto) in zip(cols, RESPUESTAS.items()):
                if col.button(texto, key=f"{sol.id}-{clave}"):
                    _responder(sol.id, clave)

    st.subheader("En cola y vencidas")
    st.dataframe(
        [
            {"Estado": s.estado, "Monto": f"{s.operacion.monto} {s.operacion.desde}",
             "Categoría": s.operacion.categoria, "Motivo": s.motivo, "Vence (UTC)": f"{s.vence:%H:%M:%S}"}
            for s in solicitudes
            if s.estado != "pendiente"
        ],
        hide_index=True,
        width="stretch",
    )
    estado.pendiente_diseno()
