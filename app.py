"""Punto de entrada: `streamlit run app.py`.

Carga el .env, obtiene banco/mercado/reloj desde banco/fabrica.py (por defecto BANCO_MODO=fakes)
y muestra las 6 pantallas. Si un módulo aún no está implementado, la pantalla muestra
un aviso con el responsable en vez de romperse.
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402

from ui import bandeja, cierre, estado, operaciones, pago, politica, rutas  # noqa: E402

PANTALLAS = {
    "Llega el pago": pago.render,
    "Rutas": rutas.render,
    "Operaciones": operaciones.render,
    "Bandeja": bandeja.render,
    "Política": politica.render,
    "Cierre del mes": cierre.render,
}


def barra_lateral() -> str:
    s = st.session_state
    st.sidebar.title("Agente de cobro")
    st.sidebar.caption("Freelancers que cobran en USD · reto Belo")
    eleccion = st.sidebar.radio("Pantallas", list(PANTALLAS))
    st.sidebar.divider()
    st.sidebar.write(f"Modo banco: `{s['modo']}`")
    if estado.fuente_actual() == "simulado":
        st.sidebar.warning("🧪 Datos simulados")
    reloj = s["reloj"]
    st.sidebar.write(f"Hoy: {reloj.hoy():%d/%m/%Y} · {reloj.ahora():%H:%M:%S} UTC")
    if hasattr(reloj, "avanzar_segundos"):
        c1, c2 = st.sidebar.columns(2)
        if c1.button("+61 s"):
            reloj.avanzar_segundos(61)
        if c2.button("+1 día"):
            reloj.avanzar(1)
    if "fabrica" in s["avisos"]:
        st.sidebar.error(s["avisos"]["fabrica"])
    return eleccion


def main() -> None:
    st.set_page_config(page_title="Agente de cobro · Belo", page_icon="💸", layout="wide")
    estado.inicializar()
    eleccion = barra_lateral()
    try:
        PANTALLAS[eleccion]()
    except NotImplementedError as e:
        estado.aviso_pendiente(str(e))


if __name__ == "__main__":
    main()
