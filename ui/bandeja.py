"""Pantalla 4: Bandeja de aprobaciones (control humano)."""

from html import escape

import streamlit as st

from ui import componentes as c
from ui import estado

RESPUESTAS = {"solo_esta_vez": "Solo esta vez", "siempre": "Siempre en este rango", "nunca": "Nunca"}
AYUDAS = {
    "solo_esta_vez": "Aprueba esta operación; tus reglas no cambian.",
    "siempre": "Aprueba y el agente aprende a permitir montos como este sin preguntarte.",
    "nunca": "Rechaza y el agente aprende a bloquear operaciones como esta.",
}


def _responder(solicitud_id: str, respuesta: str) -> None:
    from motor.politica import aplicar_cambio

    cambio = estado.intentar(st.session_state["bandeja"].responder, solicitud_id, respuesta)
    if cambio is not None:
        st.session_state["politica"] = estado.intentar(
            aplicar_cambio, st.session_state["politica"], cambio, respaldo=lambda: st.session_state["politica"]
        )


def render() -> None:
    reloj = st.session_state["reloj"]
    pol = estado.politica()
    c.encabezado("Bandeja", "Lo que supera tus límites espera tu permiso. Si no respondes a tiempo, no se ejecuta nada.",
                 simulado=estado.fuente_actual() == "simulado")
    estado.intentar(st.session_state["bandeja"].actualizar_vencidas)
    solicitudes = estado.solicitudes()

    c.chips([
        ("Hora", f"{reloj.ahora():%H:%M:%S} UTC"),
        ("Vencen en", f"{pol.vence_en_segundos} s"),
        ("Máximo", f"{pol.max_interrupciones_dia} interrupciones al día"),
    ])

    pendientes = [s for s in solicitudes if s.estado == "pendiente"]
    c.seccion(f"Esperando tu respuesta ({len(pendientes)})")
    if not pendientes:
        st.caption("No hay nada pendiente. El agente sigue solo dentro de tus reglas.")
    for sol in pendientes:
        op = sol.operacion
        quedan = max(int((sol.vence - reloj.ahora()).total_seconds()), 0)
        total = max(pol.vence_en_segundos, 1)
        with st.container(border=True, key=f"card_bandeja_{sol.id}"):
            izq, der = st.columns([3, 1])
            with izq:
                st.markdown(
                    f'{c.insignia_estado("pendiente")}'
                    f'<div style="font-size:1.7rem;font-weight:800;margin-top:6px">{escape(c.monto_op(op))}</div>'
                    f'<div style="color:#5f6b65">{escape(op.categoria.capitalize())} · {escape(sol.motivo)}</div>',
                    unsafe_allow_html=True,
                )
            with der:
                st.markdown(
                    f'<div style="text-align:right;color:#5f6b65;font-size:.85rem">Vence en</div>'
                    f'<div style="text-align:right;font-size:1.6rem;font-weight:800">{quedan} s</div>',
                    unsafe_allow_html=True,
                )
            st.progress(min(quedan / total, 1.0))
            cols = st.columns(3)
            for col, (clave, texto) in zip(cols, RESPUESTAS.items()):
                tipo = "primary" if clave == "solo_esta_vez" else "secondary"
                if col.button(texto, key=f"{sol.id}-{clave}", type=tipo, width="stretch", help=AYUDAS[clave]):
                    _responder(sol.id, clave)

    resto = [s for s in solicitudes if s.estado != "pendiente"]
    c.seccion("Historial")
    if not resto:
        st.caption("Todavía no hay solicitudes respondidas, en cola ni vencidas.")
    for sol in resto:
        c.fila(
            f"{c.monto_op(sol.operacion)} · {sol.operacion.categoria.capitalize()}",
            sol.motivo,
            f"vence {sol.vence:%H:%M:%S} UTC",
            insignia=c.insignia_estado(sol.estado),
        )
