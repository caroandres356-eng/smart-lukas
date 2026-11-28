"""Sistema visual común de las gráficas de Smart Lukas.

Todas las figuras pasan por `aplicar()` para verse como un mismo sistema.

Decisiones:
- El estilo se pone directo en el layout (no como plantilla), porque st.plotly_chart con el tema
  de Streamlit reemplaza la plantilla pero respeta lo que el layout trae explícito.
- Los textos generales NO llevan color fijo: así Streamlit los pinta bien en tema claro y oscuro.
  Solo el texto secundario usa un gris medio legible sobre ambos fondos.
- Énfasis: la ruta elegida en verde y todo lo demás en gris (es "resaltar una", no una paleta categórica).
"""

from __future__ import annotations

from decimal import Decimal

import plotly.graph_objects as go

from motor.rutas import RUTA_A, RUTA_B, RUTA_C, fmt_cop, fmt_usd

# --------------------------------------------------------------------------- colores

VERDE = "#2e7d32"  # ruta elegida / lo que se decide (igual que ui/rutas.py)
GRIS = "#9e9e9e"  # rutas no elegidas
GRIS_A = "#7a7a7a"  # en líneas, «Todo hoy» y «Mitad y mitad» llevan dos grises distintos
GRIS_C = "#b5b5b5"  # para poder distinguirlas entre sí
GRIS_OSCURO = "#616161"  # reservas (impuestos)
GRIS_CLARO = "#cfcfcf"  # reservas (colchón)
TEXTO_SECUNDARIO = "#8a8a8a"  # subtítulos, ejes y notas: legible en claro y en oscuro
REJILLA = "rgba(128,128,128,0.18)"  # línea de cuadrícula muy suave
EJE = "rgba(128,128,128,0.45)"
TINTA_CLARA = "#ffffff"  # texto dentro de rellenos oscuros
TINTA_OSCURA = "#0b0b0b"  # texto dentro de rellenos claros

FUENTE = 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'

LETRAS = {RUTA_A: "A", RUTA_B: "B", RUTA_C: "C"}
ROTULO_SIMULADO = "Datos simulados"


# --------------------------------------------------------------------------- formato


def pesos(valor: Decimal) -> str:
    """Decimal -> "$2.612.480" (usa el formato del motor; ui.estado.fmt_cop importa Streamlit)."""
    signo = "-" if valor < 0 else ""
    return f"{signo}${fmt_cop(abs(valor))}"


def pesos_con_signo(valor: Decimal) -> str:
    """Decimal -> "+$6.949" / "-$1.200" / "$0"."""
    if valor == 0:
        return "$0"
    return ("+" if valor > 0 else "-") + f"${fmt_cop(abs(valor))}"


def dolares(valor: Decimal) -> str:
    """Decimal -> "650 USD" o "454,55 USD"."""
    return f"{fmt_usd(valor)} USD"


def eje_pesos(maximo: float, paso: float = 500_000) -> tuple[list[float], list[str]]:
    """Marcas de eje en millones con formato colombiano: $0, $0,5 M, $1 M, ..."""
    valores, v = [], 0.0
    while v <= maximo:
        valores.append(v)
        v += paso
    textos = ["$0" if x == 0 else "$" + f"{x / 1e6:g}".replace(".", ",") + " M" for x in valores]
    return valores, textos


def nombre_corto(nombre_ruta: str) -> str:
    """"Lo justo hoy, el resto rindiendo" -> "B · Lo justo hoy, el resto rindiendo"."""
    letra = LETRAS.get(nombre_ruta)
    return f"{letra} · {nombre_ruta}" if letra else nombre_ruta


# --------------------------------------------------------------------------- figura


def aplicar(fig: go.Figure, titulo: str, subtitulo: str = "", alto: int = 360) -> go.Figure:
    """Estilo común: título con la conclusión, subtítulo en gris (termina en "Datos simulados") y poco ruido."""
    # El rótulo "Datos simulados" va al final del subtítulo: así nunca choca con él en pantallas angostas.
    subtitulo = f"{subtitulo} · {ROTULO_SIMULADO}" if subtitulo else ROTULO_SIMULADO
    texto_titulo = f"<b>{titulo}</b><br><span style='font-size:13px;color:{TEXTO_SECUNDARIO}'>{subtitulo}</span>"
    fig.update_layout(
        title=dict(text=texto_titulo, x=0, xanchor="left", xref="container", yref="container", y=1, yanchor="top",
                   pad=dict(t=18, l=8), font=dict(size=18)),
        font=dict(family=FUENTE, size=13),
        separators=",.",  # formato colombiano en ejes: 2.612.480 y 0,5
        height=alto,
        margin=dict(l=8, r=24, t=90, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        hoverlabel=dict(font=dict(family=FUENTE, size=13), bordercolor="rgba(0,0,0,0)"),
        bargap=0.45,
        barcornerradius=4,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, linecolor=EJE, ticks="", tickfont=dict(color=TEXTO_SECUNDARIO))
    fig.update_yaxes(gridcolor=REJILLA, gridwidth=1, zeroline=False, ticks="", tickfont=dict(color=TEXTO_SECUNDARIO))
    return fig


# Configuración para st.plotly_chart(..., config=CONFIG): sin barra de herramientas ni logo.
CONFIG = {"displayModeBar": False, "displaylogo": False}
