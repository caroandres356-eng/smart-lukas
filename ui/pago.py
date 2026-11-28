"""Pantalla: Llega el pago. Qué llegó, con qué tasas y qué se aparta antes de decidir."""

from html import escape

import streamlit as st

from fakes import fakes
from ui import componentes as c
from ui import estado
from viz.flujo import opciones_flujo


def render() -> None:
    s = st.session_state
    banco = s["banco"]
    c.encabezado("Llega el pago", "Antes de convertir nada, el agente aparta lo que no se toca.",
                 simulado=estado.fuente_actual() == "simulado")

    ingresos = [m for m in banco.movimientos() if m.tipo == "ingreso"]
    ingreso = ingresos[-1] if ingresos else fakes.cargar_ingreso_ejemplo()
    cot = banco.cotizacion("USD", "COP")
    rend = banco.rendimiento("USDT")
    c.cifra_principal("Llegó un pago", c.dolares(ingreso.monto, ingreso.moneda),
                      f"{c.fecha_corta(ingreso.fecha)} · {escape(ingreso.descripcion)}")

    saldos = "".join(
        f"<div class='sl-kpi'><div class='k'>Saldo en {s.moneda}</div>"
        f"<div class='v'>{c.pesos(s.monto) if s.moneda == 'COP' else c.fmt_usd(s.monto)}"
        f"{'' if s.moneda == 'COP' else f' <small>{s.moneda}</small>'}</div></div>"
        for s in banco.saldos()
    )
    c._html(
        "<div class='sl-kpis'>" + saldos +
        f"<div class='sl-kpi'><div class='k'>Mercado hoy</div><div class='v'>{c.pesos(cot.tasa)}</div>"
        f"<div class='d'>TRM · spread de Belo {cot.spread * 100:.0f} % · USDT rinde {rend.tasa_anual * 100:.0f} % anual</div></div>"
        "</div>"
    )

    pol = estado.politica()
    prop = estado.propuesta()
    with st.container(border=True, key="card_pago_flujo"):
        c._html("<div class='sl-ct'><h2>Así se reparte tu pago</h2>"
                f"<p>El {pol.impuestos_pct} % se guarda en USDT para impuestos y {c.dolares(pol.colchon_usd)} quedan de colchón. "
                "Del disponible, la ruta elegida convierte hoy lo justo para tus gastos.</p></div>")
        c.echarts(opciones_flujo(prop, pol), alto=340, clave="pago_flujo")
