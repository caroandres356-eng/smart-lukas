"""Pantalla 5: Política (reglas claras definidas por la persona)."""

import streamlit as st

from core.modelos import CambioPolitica
from ui import componentes as c
from ui import estado

TIPOS = {"conversion": "conversión", "pago": "pago"}


def _frase(regla: CambioPolitica) -> tuple[str, str]:
    """(frase, clase de la insignia) para una regla aprendida."""
    que = f"{TIPOS.get(regla.tipo, regla.tipo)} de {regla.categoria}"
    if regla.accion == "permitir_hasta" and regla.monto_max_usd is not None:
        return f"Permitir {que} hasta {c.dolares(regla.monto_max_usd)} sin preguntarte", "ok"
    return f"Nunca hacer {que}", "bad"


def render() -> None:
    c.encabezado("Política", "Tus reglas. El agente nunca las rompe y te avisa siempre que una aplica.",
                 simulado=estado.fuente_actual() == "simulado")
    if "politica" in st.session_state.get("avisos", {}):
        estado.aviso_pendiente(st.session_state["avisos"]["politica"])
    pol = estado.politica()

    c.seccion("Límites sin aprobación")
    c1, c2 = st.columns(2)
    with c1:
        c.tarjeta("Por operación", c.dolares(pol.auto_max_usd_por_operacion), "Más que esto va a tu bandeja")
    with c2:
        c.tarjeta("Por día", c.dolares(pol.auto_max_usd_por_dia), "Suma de las conversiones del día")

    c.seccion("Reservas")
    c3, c4 = st.columns(2)
    with c3:
        c.tarjeta("Impuestos", f"{pol.impuestos_pct} %", "Del ingreso, guardado en USDT")
    with c4:
        c.tarjeta("Colchón", c.dolares(pol.colchon_usd), "Se queda en USD y nunca se convierte")

    c.seccion("Bandeja")
    c5, c6 = st.columns(2)
    with c5:
        c.tarjeta("Las solicitudes vencen en", f"{pol.vence_en_segundos} s", "Sin respuesta, no se ejecuta nada")
    with c6:
        c.tarjeta("Interrupciones al día", f"máx. {pol.max_interrupciones_dia}", "Las demás esperan en cola")

    c.seccion("Gastos fijos")
    cols = st.columns(max(len(pol.gastos_fijos), 1))
    for col, gasto in zip(cols, pol.gastos_fijos):
        with col:
            c.tarjeta(gasto.nombre.capitalize(), c.pesos(gasto.monto_cop), f"Se paga el día {gasto.dia}")

    c.seccion("Lo que el agente aprendió")
    if pol.reglas_aprendidas:
        for regla in pol.reglas_aprendidas:
            frase, clase = _frase(regla)
            c.fila(frase, "Aprendida de tu respuesta en la bandeja", "", insignia=c.pill("Regla aprendida", clase))
    else:
        st.caption("Todavía nada. Responde «Siempre en este rango» o «Nunca» en la bandeja y aparecerá aquí.")

    with st.expander("Ver la política como JSON"):
        st.json(pol.model_dump(mode="json"))
