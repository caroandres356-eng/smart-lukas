"""Punto de entrada: `streamlit run app.py`.

Carga el .env, obtiene banco/mercado/reloj desde banco/fabrica.py (por defecto BANCO_MODO=fakes)
y muestra las pantallas con navegación arriba. Si un módulo aún no está implementado, la pantalla
muestra un aviso con el responsable en vez de romperse.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from dotenv import load_dotenv

load_dotenv()

import streamlit as st  # noqa: E402

from ui import bandeja, cierre, componentes, estado, operaciones, pago, politica, rutas  # noqa: E402

MARCA = Path(__file__).parent / "ui" / "marca.svg"

# (título, función, ícono, ruta en la URL)
PANTALLAS: list[tuple[str, Callable[[], None], str, str]] = [
    ("Llega el pago", pago.render, ":material/payments:", "pago"),
    ("Rutas", rutas.render, ":material/alt_route:", "rutas"),
    ("Operaciones", operaciones.render, ":material/swap_horiz:", "operaciones"),
    ("Bandeja", bandeja.render, ":material/inbox:", "bandeja"),
    ("Política", politica.render, ":material/tune:", "politica"),
    ("Cierre", cierre.render, ":material/task_alt:", "cierre"),
]


def _segura(render: Callable[[], None]) -> Callable[[], None]:
    """Envuelve una pantalla: si algo aún no está implementado, muestra el aviso en vez de romperse."""

    def pantalla() -> None:
        try:
            render()
        except NotImplementedError as e:
            estado.aviso_pendiente(str(e))

    return pantalla


def barra_simulacion() -> None:
    """Controles del reloj en un popover discreto, arriba a la derecha (la insignia de datos simulados va en cada pantalla)."""
    s = st.session_state
    reloj = s["reloj"]
    _, der = st.columns([5, 2], vertical_alignment="center")
    with der:
        with st.popover(f"Simulación · {reloj.hoy():%d/%m/%Y}", icon=":material/schedule:", width="stretch"):
            st.caption(f"Banco: `{s['modo']}` · {reloj.ahora():%H:%M:%S} UTC")
            if hasattr(reloj, "avanzar_segundos"):
                c1, c2 = st.columns(2)
                if c1.button("+61 s", width="stretch", help="Adelanta el reloj para ver vencer una solicitud"):
                    reloj.avanzar_segundos(61)
                if c2.button("+1 día", width="stretch"):
                    reloj.avanzar(1)
            st.caption("Hackathon 30X · reto Banca agéntica de Belo")
    if "fabrica" in s["avisos"]:
        st.error(s["avisos"]["fabrica"])


def main() -> None:
    st.set_page_config(page_title="Smart Lukas", page_icon=":material/savings:", layout="wide")
    componentes.inyectar_css()
    estado.inicializar()
    st.logo(str(MARCA), size="large")

    paginas = [
        st.Page(_segura(fn), title=titulo, icon=icono, url_path=ruta, default=i == 0)
        for i, (titulo, fn, icono, ruta) in enumerate(PANTALLAS)
    ]
    pagina = st.navigation(paginas, position="top")
    barra_simulacion()
    pagina.run()


if __name__ == "__main__":
    main()
