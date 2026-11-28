"""Pantalla 5: Política (reglas claras definidas por la persona)."""

from decimal import Decimal
from html import escape

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


def _barra(valor: Decimal, limite: Decimal, texto: str) -> str:
    """Barra de uso del límite: verde si cabe, ámbar si lo supera (esa operación pide permiso)."""
    supera = valor > limite
    ancho = 100 if supera or limite <= 0 else float(valor / limite * 100)
    color = "#c98a1b" if supera else "#2e7d32"
    aviso = " · supera el límite, pide permiso" if supera else " · dentro del límite"
    return (f"<div style='height:9px;background:#eef1ef;border-radius:999px;overflow:hidden;margin:8px 0 6px'>"
            f"<div style='width:{ancho:.0f}%;height:100%;background:{color};border-radius:999px'></div></div>"
            f"{escape(texto)}<b style='color:{'#7a4a00' if supera else '#1f5f24'}'>{aviso}</b>")


def render() -> None:
    c.encabezado("Política", "Tus reglas. El agente nunca las rompe y te avisa siempre que una aplica.",
                 simulado=estado.fuente_actual() == "simulado")
    if "politica" in st.session_state.get("avisos", {}):
        estado.aviso_pendiente(st.session_state["avisos"]["politica"])
    pol = estado.politica()

    c.seccion("Límites sin aprobación")
    # Cómo encaja el plan del motor en tus límites (solo se comparan montos de la propuesta con la política).
    prop = estado.propuesta()
    a_pesos = [v.operacion for v in prop.veredictos if v.operacion.hacia == "COP" and v.estado != "bloqueada"]
    mayor = max(a_pesos, key=lambda o: o.monto, default=None)
    por_dia: dict = {}
    for o in a_pesos:
        por_dia[o.fecha_programada] = por_dia.get(o.fecha_programada, Decimal(0)) + o.monto
    dia_max = max(por_dia, key=por_dia.get, default=None)
    c1, c2 = st.columns(2)
    with c1:
        detalle = "Más que esto va a tu bandeja"
        if mayor:
            detalle = _barra(mayor.monto, pol.auto_max_usd_por_operacion,
                             f"La mayor del plan: {c.dolares(mayor.monto)} ({mayor.categoria})")
        c.tarjeta("Por operación", c.dolares(pol.auto_max_usd_por_operacion), detalle)
    with c2:
        detalle = "Suma de las conversiones del día"
        if dia_max:
            detalle = _barra(por_dia[dia_max], pol.auto_max_usd_por_dia,
                             f"El día con más conversiones ({c.fecha_corta(dia_max)}): {c.dolares(por_dia[dia_max])}")
        c.tarjeta("Por día", c.dolares(pol.auto_max_usd_por_dia), detalle)

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
