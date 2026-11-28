"""Pantalla: Operaciones. El calendario del mes (interactivo) y la lista de veredictos con su motivo."""

from html import escape

import streamlit as st

from ui import calendario, estado
from ui import componentes as c

TIPOS_MOVIMIENTO = {"ingreso": "Ingreso", "conversion": "Conversión", "pago": "Pago", "rendimiento": "Rendimiento"}


def render() -> None:
    c.encabezado("Operaciones", "Lo que hará el agente con tu pago: cada operación pasa por tus reglas y lleva su motivo.",
                 simulado=estado.fuente_actual() == "simulado")
    prop = estado.propuesta()
    pol = estado.politica()
    hoy = st.session_state["reloj"].hoy()
    conteo = calendario.resumen(prop)

    c._html(
        "<div class='sl-kpis'>"
        f"<div class='sl-kpi'><div class='k'>Operaciones del plan</div><div class='v'>{conteo['total']}</div>"
        f"<div class='d'>Ruta «{escape(prop.elegida)}»</div></div>"
        f"<div class='sl-kpi'><div class='k'>Se hacen solas {c.insignia_estado('auto')}</div><div class='v'>{conteo['auto']}</div>"
        "<div class='d'>Dentro de tus límites</div></div>"
        f"<div class='sl-kpi{' warn' if conteo['requiere_aprobacion'] else ''}'><div class='k'>Esperan tu permiso</div>"
        f"<div class='v'>{conteo['requiere_aprobacion']}</div><div class='d'>Van a tu bandeja</div></div>"
        f"<div class='sl-kpi'><div class='k'>Bloqueadas {c.insignia_estado('bloqueada')}</div><div class='v'>{conteo['bloqueada']}</div>"
        "<div class='d'>No se ejecutan</div></div></div>"
    )

    with st.container(border=True, key="card_ops_cal"):
        c._html(f"<div class='sl-ct'><h2>Calendario del mes</h2><p>Hoy es {c.fecha_corta(hoy)} en la simulación. "
                "Pasa el cursor por una operación para ver su detalle; usa «+1 día» para ver cómo avanzan.</p></div>")
        c._html("<div class='sl-leyenda' style='margin-top:10px'>"
                "<span><i style='background:#2e7d32'></i>Automática</span>"
                "<span><i style='background:#fff;border:2.5px solid #c98a1b;box-sizing:border-box'></i>Requiere tu permiso</span>"
                "<span><i style='background:#b3261e;border-radius:2px'></i>Bloqueada</span>"
                "<span><i style='background:#f1f3f2;border:1px solid #c9d1cd;border-radius:3px'></i>Pago de un gasto fijo</span></div>")
        c._html(calendario.html_calendario(prop, pol, hoy))

    with st.container(border=True, key="card_ops_lista"):
        c._html("<div class='sl-ct'><h2>Todas las operaciones, en orden</h2>"
                "<p>Estado según tus reglas y momento según el reloj de simulación.</p></div>")
        for v in prop.veredictos:
            op = v.operacion
            _, cuando = calendario.momento(v, hoy)
            c.fila(f"{c.monto_op(op)} · {op.categoria.capitalize()}", v.motivo,
                   f"{c.fecha_corta(op.fecha_programada)} · {cuando}", insignia=c.insignia_estado(v.estado))

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
