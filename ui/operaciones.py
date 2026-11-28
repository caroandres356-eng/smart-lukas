"""Pantalla 3: Operaciones con su veredicto (auto / requiere aprobación / bloqueada)."""

import streamlit as st

from ui import componentes as c
from ui import estado

TIPOS_MOVIMIENTO = {"ingreso": "Ingreso", "conversion": "Conversión", "pago": "Pago", "rendimiento": "Rendimiento"}


def render() -> None:
    c.encabezado("Operaciones", "Cada operación de la ruta elegida pasa por tus reglas, siempre con un motivo.",
                 simulado=estado.fuente_actual() == "simulado")
    prop = estado.propuesta()

    conteo = {e: sum(1 for v in prop.veredictos if v.estado == e) for e in ("auto", "requiere_aprobacion", "bloqueada")}
    cols = st.columns(3)
    with cols[0]:
        c.tarjeta("Automáticas", str(conteo["auto"]), "Dentro de tus límites", insignia=c.insignia_estado("auto"))
    with cols[1]:
        c.tarjeta("Requieren aprobación", str(conteo["requiere_aprobacion"]), "Van a tu bandeja",
                  resaltada=conteo["requiere_aprobacion"] > 0, insignia=c.insignia_estado("requiere_aprobacion"))
    with cols[2]:
        c.tarjeta("Bloqueadas", str(conteo["bloqueada"]), "No se ejecutan", insignia=c.insignia_estado("bloqueada"))

    c.seccion(f"Plan de la ruta «{prop.elegida}»")
    for v in prop.veredictos:
        op = v.operacion
        c.fila(
            f"{c.monto_op(op)} · {op.categoria.capitalize()}",
            v.motivo,
            c.fecha_corta(op.fecha_programada),
            insignia=c.insignia_estado(v.estado),
        )

    with st.expander("Movimientos del banco"):
        st.dataframe(
            [
                {
                    "Fecha": c.fecha_corta(m.fecha),
                    "Tipo": TIPOS_MOVIMIENTO.get(m.tipo, m.tipo),
                    "Monto": c.pesos(m.monto) if m.moneda == "COP" else c.dolares(m.monto, m.moneda),
                    "Descripción": m.descripcion,
                }
                for m in st.session_state["banco"].movimientos()
            ],
            hide_index=True,
            width="stretch",
        )
