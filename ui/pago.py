"""Pantalla 1: Llega el pago."""

from html import escape

import streamlit as st

from fakes import fakes
from ui import componentes as c
from ui import estado
from viz.estilo import CONFIG
from viz.reparto import grafica_reparto


def render() -> None:
    s = st.session_state
    banco = s["banco"]
    c.encabezado("Llega el pago", "Antes de convertir nada, el agente aparta lo que no se toca.",
                 simulado=estado.fuente_actual() == "simulado")

    ingresos = [m for m in banco.movimientos() if m.tipo == "ingreso"]
    ingreso = ingresos[-1] if ingresos else fakes.cargar_ingreso_ejemplo()
    c.cifra_principal(
        "Llegó un pago",
        c.dolares(ingreso.monto, ingreso.moneda),
        f"{ingreso.fecha:%d/%m/%Y} · {escape(ingreso.descripcion)}",
    )

    cot = banco.cotizacion("USD", "COP")
    rend = banco.rendimiento("USDT")
    c.chips([
        ("TRM hoy", c.pesos(cot.tasa)),
        ("Spread de Belo", f"{cot.spread * 100:.0f} %"),
        ("Rendimiento USDT", f"{rend.tasa_anual * 100:.0f} % anual"),
    ])

    c.seccion("Tus saldos")
    cols = st.columns(3)
    for col, saldo in zip(cols, banco.saldos()):
        valor = c.pesos(saldo.monto) if saldo.moneda == "COP" else c.dolares(saldo.monto, saldo.moneda)
        with col:
            c.tarjeta(saldo.moneda, valor)

    pol = estado.politica()
    c.seccion("Qué se separa antes de decidir")
    with st.container(border=True):
        st.plotly_chart(grafica_reparto(ingreso, pol), width="stretch", config=CONFIG)
        st.caption(
            f"Impuestos: el {pol.impuestos_pct} % se guarda en USDT. "
            f"Colchón: {c.dolares(pol.colchon_usd)} que nunca se convierten. El resto lo comparan las 3 rutas."
        )
