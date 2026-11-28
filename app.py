"""Punto de entrada: `streamlit run app.py`.

Carga el .env, obtiene banco/mercado/reloj desde banco/fabrica.py (por defecto BANCO_MODO=fakes)
y muestra las 6 pantallas. Si un módulo aún no está implementado, la pantalla muestra
un aviso con el responsable en vez de romperse.
"""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402

from ui import bandeja, cierre, componentes, estado, operaciones, pago, politica, rutas  # noqa: E402

PANTALLAS = {
    "Llega el pago": pago.render,
    "Rutas": rutas.render,
    "Operaciones": operaciones.render,
    "Bandeja": bandeja.render,
    "Política": politica.render,
    "Cierre del mes": cierre.render,
}

ICONOS = {
    "Llega el pago": ":material/payments:",
    "Rutas": ":material/alt_route:",
    "Operaciones": ":material/swap_horiz:",
    "Bandeja": ":material/inbox:",
    "Política": ":material/tune:",
    "Cierre del mes": ":material/task_alt:",
}


def barra_lateral() -> str:
    s = st.session_state
    sb = st.sidebar
    sb.markdown(
        '<div class="sl-brand">Smart <span>Lukas</span></div>'
        '<div class="sl-tag">Agente de cobro para freelancers que cobran en USD</div>',
        unsafe_allow_html=True,
    )
    eleccion = sb.radio(
        "Pantallas", list(PANTALLAS), format_func=lambda p: f"{ICONOS[p]}  {p}", label_visibility="collapsed"
    )
    sb.divider()

    reloj = s["reloj"]
    with sb.container(border=True):
        st.markdown(
            f"**Simulación** &nbsp; {componentes.pill('● Datos simulados', 'sim') if estado.fuente_actual() == 'simulado' else ''}",
            unsafe_allow_html=True,
        )
        st.caption(f"Banco: `{s['modo']}` · Hoy {reloj.hoy():%d/%m/%Y} · {reloj.ahora():%H:%M:%S} UTC")
        if hasattr(reloj, "avanzar_segundos"):
            c1, c2 = st.columns(2)
            if c1.button("+61 s", width="stretch", help="Adelanta el reloj para ver vencer una solicitud"):
                reloj.avanzar_segundos(61)
            if c2.button("+1 día", width="stretch"):
                reloj.avanzar(1)
    if "fabrica" in s["avisos"]:
        sb.error(s["avisos"]["fabrica"])
    sb.caption("Hackathon 30X · reto Banca agéntica de Belo")
    return eleccion


def main() -> None:
    st.set_page_config(page_title="Smart Lukas", page_icon=":material/savings:", layout="wide")
    componentes.inyectar_css()
    estado.inicializar()
    eleccion = barra_lateral()
    try:
        PANTALLAS[eleccion]()
    except NotImplementedError as e:
        estado.aviso_pendiente(str(e))


if __name__ == "__main__":
    main()
