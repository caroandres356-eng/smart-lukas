"""Pantalla 5: Política (reglas claras definidas por la persona)."""

import streamlit as st

from ui import estado


def render() -> None:
    st.title("📜 Política")
    if "politica" in st.session_state.get("avisos", {}):
        estado.aviso_pendiente(st.session_state["avisos"]["politica"])
    pol = estado.politica()

    c1, c2 = st.columns(2)
    c1.metric("Máx. por operación sin aprobación", estado.fmt_usd(pol.auto_max_usd_por_operacion))
    c2.metric("Máx. por día sin aprobación", estado.fmt_usd(pol.auto_max_usd_por_dia))
    c3, c4 = st.columns(2)
    c3.metric("Impuestos (en USDT)", f"{pol.impuestos_pct} %")
    c4.metric("Colchón que nunca se convierte", estado.fmt_usd(pol.colchon_usd))
    st.write(f"Las solicitudes vencen en **{pol.vence_en_segundos} s** · máximo **{pol.max_interrupciones_dia}** interrupciones al día.")

    st.subheader("Gastos fijos")
    st.dataframe(
        [{"Gasto": g.nombre, "Monto": estado.fmt_cop(g.monto_cop), "Día": g.dia} for g in pol.gastos_fijos],
        hide_index=True,
        width="stretch",
    )

    st.subheader("Lo que el agente aprendió")
    if pol.reglas_aprendidas:
        st.dataframe([r.model_dump(mode="json") for r in pol.reglas_aprendidas], hide_index=True, width="stretch")
    else:
        st.caption("Todavía nada. Responde «Siempre en este rango» o «Nunca» en la bandeja.")

    with st.expander("Ver como JSON"):
        st.json(pol.model_dump(mode="json"))
    estado.pendiente_diseno()
