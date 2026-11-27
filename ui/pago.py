"""Pantalla 1: Llega el pago."""

import streamlit as st

from fakes import fakes
from ui import estado


def render() -> None:
    st.title("💵 Llega el pago")
    s = st.session_state
    banco = s["banco"]
    estado.etiqueta_fuente(estado.fuente_actual())

    ingresos = [m for m in banco.movimientos() if m.tipo == "ingreso"]
    ingreso = ingresos[-1] if ingresos else fakes.cargar_ingreso_ejemplo()
    st.success(f"Llegó un pago de **{estado.fmt_usd(ingreso.monto, ingreso.moneda)}** el {ingreso.fecha:%d/%m/%Y}: {ingreso.descripcion}")

    st.subheader("Saldos")
    cols = st.columns(3)
    for col, saldo in zip(cols, banco.saldos()):
        valor = estado.fmt_cop(saldo.monto) if saldo.moneda == "COP" else estado.fmt_usd(saldo.monto, saldo.moneda)
        col.metric(saldo.moneda, valor)

    cot = banco.cotizacion("USD", "COP")
    rend = banco.rendimiento("USDT")
    c1, c2 = st.columns(2)
    c1.metric("TRM hoy (USD→COP)", estado.fmt_cop(cot.tasa), help=f"Spread de Belo: {cot.spread * 100:.0f} %")
    c2.metric("Rendimiento USDT", f"{rend.tasa_anual * 100:.0f} % anual")

    pol = estado.politica()
    st.subheader("Qué se separa antes de decidir")
    st.write(
        f"- Impuestos: **{pol.impuestos_pct} %** del ingreso se guarda en USDT\n"
        f"- Colchón: **{estado.fmt_usd(pol.colchon_usd)}** que nunca se convierte"
    )
    estado.pendiente_diseno()
