"""Componentes visuales de la interfaz (Persona 3): tarjetas, cifra principal, insignias y formato.

Todo es HTML + CSS propio dentro de st.markdown. Los números NO se calculan aquí: llegan ya hechos
del motor/estado y aquí solo se presentan.
"""

from __future__ import annotations

from datetime import date
from html import escape

import streamlit as st

from core.modelos import Operacion
from motor.rutas import fmt_cop, fmt_usd

VERDE = "#2e7d32"

MESES_CORTOS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")

# estado -> (ícono, texto, clase CSS). Siempre ícono + texto: el color nunca va solo.
ESTADOS = {
    "auto": ("●", "Automática", "ok"),
    "aprobada": ("✓", "Aprobada", "ok"),
    "requiere_aprobacion": ("◐", "Requiere aprobación", "warn"),
    "pendiente": ("◐", "Pendiente", "warn"),
    "en_cola": ("…", "En cola", "neutral"),
    "bloqueada": ("✕", "Bloqueada", "bad"),
    "rechazada": ("✕", "Rechazada", "bad"),
    "vencida": ("◷", "Vencida · no se ejecutó", "neutral"),
}

CSS = """
<style>
:root {
  --sl-verde: #2e7d32; --sl-verde-suave: #e8f3ea; --sl-tinta: #1b1f1d; --sl-tinta-2: #5f6b65;
  --sl-borde: #e3e8e5; --sl-tarjeta: #ffffff; --sl-ambar: #8a5a00; --sl-ambar-suave: #fff4dc;
  --sl-rojo: #b3261e; --sl-rojo-suave: #fdeceb; --sl-gris-suave: #f0f2f1;
}
.block-container { padding-top: 4.6rem; max-width: 1280px; }

/* Tarjetas de Streamlit con key="card_..." (contenedores con gráficas) */
[class*="st-key-card_"] { background:#ffffff; border:1px solid var(--sl-borde) !important; border-radius:16px !important;
  padding:20px 22px !important; box-shadow:0 1px 2px rgba(16,24,20,.04); }
[class*="st-key-card_bandeja"] { border-color:#f1dcb5 !important; box-shadow:0 4px 18px rgba(178,106,0,.08); }
.sl-ct h2 { font-size:1.12rem; font-weight:700; margin:0; padding:0; color:var(--sl-tinta); }
.sl-ct p { margin:4px 0 0; color:var(--sl-tinta-2); font-size:.92rem; }

/* Indicadores (KPI) */
.sl-kpis { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:18px; margin:6px 0 18px; }
.sl-kpi { background:#fff; border:1px solid var(--sl-borde); border-radius:16px; padding:16px 18px; box-shadow:0 1px 2px rgba(16,24,20,.04); }
.sl-kpi .k { color:var(--sl-tinta-2); font-size:.82rem; font-weight:600; display:flex; justify-content:space-between; gap:8px; align-items:center; }
.sl-kpi .v { font-size:1.85rem; font-weight:800; letter-spacing:-.02em; margin-top:6px; color:var(--sl-tinta); line-height:1.15; }
.sl-kpi .v small { font-size:1rem; font-weight:600; color:var(--sl-tinta-2); }
.sl-kpi .d { color:var(--sl-tinta-2); font-size:.82rem; margin-top:6px; }
.sl-kpi.on { border:1.5px solid var(--sl-verde); box-shadow:0 0 0 4px var(--sl-verde-suave); }
.sl-kpi.on .v { color:#1f5f24; }
.sl-kpi.warn { background:#fff8ec; border-color:#f1dcb5; }
.sl-kpi.warn .k, .sl-kpi.warn .d { color:#7a4a00; } .sl-kpi.warn .v { color:#5c3800; }
.sl-kpi .tag { white-space:nowrap; font-size:.72rem; font-weight:700; color:#1f5f24; background:var(--sl-verde-suave); padding:2px 8px; border-radius:999px; }
@media (max-width: 1000px) { .sl-kpis { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width: 560px) { .sl-kpis { grid-template-columns:1fr; } }

/* Saludo del Panel */
.sl-hola { display:flex; justify-content:space-between; align-items:flex-end; gap:16px; flex-wrap:wrap; margin:4px 0 16px; }
.sl-hola .s { color:var(--sl-tinta-2); font-size:.9rem; font-weight:500; }
.sl-hola h1 { margin:4px 0 0; padding:0; font-size:2.1rem; font-weight:700; letter-spacing:-.02em; color:var(--sl-tinta); }
.sl-hola .r { color:var(--sl-tinta-2); font-size:.9rem; max-width:440px; }
.sl-hola .r b { color:var(--sl-tinta); }

/* Mini comparación de rutas */
.sl-ruta { border:1px solid var(--sl-borde); border-radius:12px; padding:11px 13px; margin-top:10px; }
.sl-ruta.on { border:1.5px solid var(--sl-verde); background:#f6fbf7; }
.sl-ruta.off { border-style:dashed; background:#fafbfa; }
.sl-ruta .t { display:flex; justify-content:space-between; align-items:center; gap:8px; font-size:.88rem; }
.sl-ruta .t b { display:inline-flex; align-items:center; gap:8px; }
.sl-ruta .pt { width:10px; height:10px; border-radius:999px; flex-shrink:0; }
.sl-ruta .n { color:var(--sl-tinta-2); font-size:.82rem; margin-top:6px; }
.sl-ruta .bar { display:flex; align-items:center; gap:10px; margin-top:9px; }
.sl-ruta .bar > div { flex:1; height:9px; background:var(--sl-verde-suave); border-radius:999px; overflow:hidden; }
.sl-ruta .bar > div > div { height:100%; border-radius:999px; }

/* Al cierre (junto a la evolución) */
.sl-cierre .h { font-size:.74rem; font-weight:700; color:var(--sl-tinta-2); text-transform:uppercase; letter-spacing:.05em; margin-bottom:6px; }
.sl-cierre .it { margin:12px 0; }
.sl-cierre .l { display:flex; align-items:center; gap:8px; font-size:.84rem; color:#33403a; }
.sl-cierre .l span { width:10px; height:10px; border-radius:999px; }
.sl-cierre .v { font-size:1.2rem; font-weight:800; margin-top:2px; }
.sl-cierre .b { display:flex; align-items:center; gap:8px; margin-top:4px; font-size:.76rem; color:var(--sl-tinta-2); }
.sl-cierre .b div { height:8px; border-radius:4px; }

/* Calendario del mes */
.sl-cal-wrap { overflow-x:auto; margin-top:14px; }
.sl-cal { display:grid; grid-template-columns:repeat(7,minmax(0,1fr)); gap:8px; min-width:900px; }
.sl-cal .wd { font-size:.72rem; font-weight:700; color:var(--sl-tinta-2); text-transform:uppercase; letter-spacing:.05em; padding:0 4px 2px; }
.sl-cal .wd.hl { color:#1f5f24; }
.sl-cal .day { min-height:92px; border:1px solid #e9eeeb; border-radius:12px; padding:8px; background:#fbfcfb; display:flex; flex-direction:column; gap:6px; }
.sl-cal .day.out { background:transparent; border-style:dashed; border-color:#eef1ef; }
.sl-cal .day.out .dn { color:#b0b9b4; }
.sl-cal .day.hot { background:#fff; border-color:#cfe3d2; box-shadow:0 2px 10px rgba(46,125,50,.08); }
.sl-cal .day.today { border:1.5px solid var(--sl-verde); }
.sl-cal .dn { font-size:.8rem; font-weight:700; color:#33403a; }
.sl-cal .dh { display:flex; justify-content:space-between; align-items:center; gap:6px; }
.sl-cal .tag { font-size:.68rem; font-weight:700; color:#fff; background:var(--sl-verde); padding:2px 7px; border-radius:999px; white-space:nowrap; }
.sl-cal .chip { display:flex; gap:7px; align-items:flex-start; border-radius:9px; padding:6px 8px; font-size:.74rem; line-height:1.3; cursor:help; }
.sl-cal .chip b { display:block; font-weight:700; color:var(--sl-tinta); }
.sl-cal .chip span { color:var(--sl-tinta-2); }
.sl-cal .chip .dot { flex:0 0 9px; height:9px; border-radius:999px; margin-top:3px; }
.sl-cal .chip.ok { background:#f1f8f2; } .sl-cal .chip.ok .dot { background:var(--sl-verde); }
.sl-cal .chip.warn { background:#fff4df; outline:1.5px solid #e7b860; }
.sl-cal .chip.warn .dot { background:#fff; border:2.5px solid #c98a1b; flex-basis:11px; height:11px; }
.sl-cal .chip.warn span { color:#7a4a00; font-weight:600; }
.sl-cal .chip.bad { background:var(--sl-rojo-suave); } .sl-cal .chip.bad .dot { background:var(--sl-rojo); border-radius:2px; }
.sl-cal .evt { font-size:.74rem; line-height:1.35; color:#33403a; background:#f1f3f2; border:1px solid #dfe5e1; border-radius:9px; padding:6px 8px; }
.sl-cal .evt b { display:block; font-size:.8rem; color:var(--sl-tinta); }
.sl-cal .evt span { display:block; color:var(--sl-tinta-2); font-size:.7rem; }
.sl-stats { display:flex; gap:12px; flex-wrap:wrap; margin-top:14px; }
.sl-stats > div { padding:10px 14px; border-radius:12px; background:#f7f9f8; border:1px solid var(--sl-borde); }
.sl-stats .n { font-size:1.35rem; font-weight:800; }
.sl-stats .t { font-size:.74rem; color:var(--sl-tinta-2); }
.sl-stats .ok { background:#f1f8f2; border-color:#d5e9d8; } .sl-stats .ok .n { color:#1f5f24; }
.sl-stats .warn { background:#fff8ec; border-color:#f1dcb5; } .sl-stats .warn .n { color:#5c3800; } .sl-stats .warn .t { color:#7a4a00; }
.sl-stats .txt { flex:1 1 280px; border-style:dashed; background:transparent; font-size:.8rem; color:#33403a; line-height:1.5; display:flex; align-items:center; }
.sl-leyenda { display:flex; gap:14px; flex-wrap:wrap; font-size:.8rem; color:#33403a; }
.sl-leyenda span { display:inline-flex; align-items:center; gap:6px; }
.sl-leyenda i { width:10px; height:10px; border-radius:999px; display:inline-block; }

/* Explicación del agente (tarjeta oscura) */
.sl-explica { background:#17201b; color:#fff; border-radius:16px; padding:20px 24px; display:flex; gap:16px; align-items:flex-start; margin-top:18px; }
.sl-explica .ic { width:40px; height:40px; border-radius:12px; background:rgba(255,255,255,.1); display:flex; align-items:center; justify-content:center; flex-shrink:0; }
.sl-explica .h { font-size:.8rem; font-weight:600; color:#9fd8a6; }
.sl-explica p { margin:6px 0 0; font-size:.95rem; line-height:1.6; color:#e7ece9; }
h1, h2, h3 { letter-spacing: -0.01em; }

/* Encabezado de pantalla */
.sl-head { display:flex; justify-content:space-between; align-items:flex-start; gap:16px; flex-wrap:wrap; margin-bottom:18px; }
.sl-head h1 { font-size:1.9rem; font-weight:700; margin:0; padding:0; color:var(--sl-tinta); }
.sl-head p { margin:4px 0 0; color:var(--sl-tinta-2); font-size:0.98rem; }

/* Insignias y chips */
.sl-pill { display:inline-flex; align-items:center; gap:6px; padding:3px 10px; border-radius:999px;
  font-size:0.8rem; font-weight:600; white-space:nowrap; border:1px solid transparent; }
.sl-pill.sim { background:var(--sl-gris-suave); color:var(--sl-tinta-2); border-color:var(--sl-borde); }
.sl-pill.ok { background:var(--sl-verde-suave); color:var(--sl-verde); }
.sl-pill.warn { background:var(--sl-ambar-suave); color:var(--sl-ambar); }
.sl-pill.bad { background:var(--sl-rojo-suave); color:var(--sl-rojo); }
.sl-pill.neutral { background:var(--sl-gris-suave); color:var(--sl-tinta-2); }
.sl-chips { display:flex; gap:8px; flex-wrap:wrap; margin:6px 0 4px; }
.sl-chip { background:var(--sl-tarjeta); border:1px solid var(--sl-borde); border-radius:999px; padding:5px 12px;
  font-size:0.86rem; color:var(--sl-tinta-2); }
.sl-chip b { color:var(--sl-tinta); }

/* Tarjetas */
.sl-card { background:var(--sl-tarjeta); border:1px solid var(--sl-borde); border-radius:14px; padding:16px 18px;
  box-shadow:0 1px 2px rgba(16,24,20,.04), 0 4px 14px rgba(16,24,20,.05); height:100%; margin-bottom:12px; }
.sl-card.on { border:1.5px solid var(--sl-verde); box-shadow:0 0 0 3px var(--sl-verde-suave), 0 4px 14px rgba(16,24,20,.06); }
.sl-card .k { color:var(--sl-tinta-2); font-size:0.84rem; font-weight:600; text-transform:uppercase; letter-spacing:.04em; }
.sl-card .v { color:var(--sl-tinta); font-size:1.6rem; font-weight:700; margin-top:4px; line-height:1.2; }
.sl-card .d { color:var(--sl-tinta-2); font-size:0.9rem; margin-top:6px; }
.sl-card .top { display:flex; justify-content:space-between; align-items:center; gap:8px; }

/* Cifra principal (una por pantalla) */
.sl-hero { background:linear-gradient(135deg, #ffffff 0%, #f1f8f2 100%); border:1px solid var(--sl-borde);
  border-radius:18px; padding:22px 26px; margin:4px 0 18px; box-shadow:0 4px 18px rgba(16,24,20,.06); }
.sl-hero .k { color:var(--sl-tinta-2); font-size:0.95rem; font-weight:600; }
.sl-hero .v { font-size:3rem; font-weight:800; line-height:1.1; color:var(--sl-tinta); margin-top:4px; }
.sl-hero .v.ok { color:var(--sl-verde); }
.sl-hero .d { color:var(--sl-tinta-2); margin-top:6px; font-size:1rem; }

/* Filas tipo lista (operaciones, historial) */
.sl-row { display:grid; grid-template-columns: 190px 1fr auto; gap:14px; align-items:center; background:var(--sl-tarjeta);
  border:1px solid var(--sl-borde); border-radius:12px; padding:12px 16px; margin-bottom:8px; }
.sl-row .m { font-weight:700; color:var(--sl-tinta); }
.sl-row .s { color:var(--sl-tinta-2); font-size:0.88rem; }
.sl-row .f { color:var(--sl-tinta-2); font-size:0.88rem; text-align:right; white-space:nowrap; }
@media (max-width: 720px) { .sl-row { grid-template-columns: 1fr; } .sl-row .f { text-align:left; } .sl-hero .v { font-size:2.3rem; } }

/* Cita (explicación del agente) */
.sl-quote { background:var(--sl-tarjeta); border:1px solid var(--sl-borde); border-left:4px solid var(--sl-verde);
  border-radius:12px; padding:16px 20px; color:var(--sl-tinta); line-height:1.6; margin:8px 0 18px; }

.sl-section { font-size:1.1rem; font-weight:700; color:var(--sl-tinta); margin:22px 0 10px; }

/* Barra lateral */
[data-testid="stSidebar"] .sl-brand { font-size:1.35rem; font-weight:800; color:var(--sl-tinta); letter-spacing:-0.01em; }
[data-testid="stSidebar"] .sl-brand span { color:var(--sl-verde); }
[data-testid="stSidebar"] .sl-tag { color:var(--sl-tinta-2); font-size:0.86rem; margin-bottom:8px; }
[data-testid="stSidebar"] div[role="radiogroup"] label { padding:7px 10px; border-radius:10px; margin-bottom:2px; width:100%; }
[data-testid="stSidebar"] div[role="radiogroup"] label:hover { background:var(--sl-gris-suave); }
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) { background:var(--sl-verde-suave); }
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p { color:var(--sl-verde); font-weight:700; }
[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child { display:none; }
</style>
"""


# --------------------------------------------------------------------------- formato


def pesos(valor) -> str:
    return ("-" if valor < 0 else "") + "$" + fmt_cop(abs(valor))


def pesos_con_signo(valor) -> str:
    if valor == 0:
        return "$0"
    return ("+" if valor > 0 else "-") + "$" + fmt_cop(abs(valor))


def dolares(valor, moneda: str = "USD") -> str:
    return f"{fmt_usd(valor)} {moneda}"


def fecha_corta(d: date) -> str:
    return f"{d.day:02d} {MESES_CORTOS[d.month - 1]}"


def monto_op(op: Operacion) -> str:
    """"450 USD → COP"."""
    destino = f" → {op.hacia}" if op.hacia else ""
    return f"{fmt_usd(op.monto)} {op.desde}{destino}"


# --------------------------------------------------------------------------- piezas


def _html(contenido: str) -> None:
    st.markdown(contenido, unsafe_allow_html=True)


def inyectar_css() -> None:
    _html(CSS)


def pill(texto: str, clase: str = "neutral") -> str:
    return f'<span class="sl-pill {clase}">{escape(texto)}</span>'


def insignia_estado(estado: str) -> str:
    icono, texto, clase = ESTADOS.get(estado, ("•", estado, "neutral"))
    return f'<span class="sl-pill {clase}">{icono} {escape(texto)}</span>'


def encabezado(titulo: str, subtitulo: str = "", simulado: bool = True) -> None:
    derecha = pill("● Datos simulados", "sim") if simulado else ""
    sub = f"<p>{escape(subtitulo)}</p>" if subtitulo else ""
    _html(f'<div class="sl-head"><div><h1>{escape(titulo)}</h1>{sub}</div>{derecha}</div>')


def cifra_principal(etiqueta: str, valor: str, detalle: str = "", positiva: bool = False) -> None:
    clase = "v ok" if positiva else "v"
    det = f'<div class="d">{detalle}</div>' if detalle else ""
    _html(f'<div class="sl-hero"><div class="k">{escape(etiqueta)}</div><div class="{clase}">{escape(valor)}</div>{det}</div>')


def tarjeta(titulo: str, valor: str, detalle: str = "", resaltada: bool = False, insignia: str = "") -> None:
    """detalle e insignia pueden traer HTML propio (ya escapado por quien llama)."""
    clase = "sl-card on" if resaltada else "sl-card"
    det = f'<div class="d">{detalle}</div>' if detalle else ""
    _html(
        f'<div class="{clase}"><div class="top"><div class="k">{escape(titulo)}</div>{insignia}</div>'
        f'<div class="v">{escape(valor)}</div>{det}</div>'
    )


def chips(pares: list[tuple[str, str]]) -> None:
    _html('<div class="sl-chips">' + "".join(f'<span class="sl-chip">{escape(k)} <b>{escape(v)}</b></span>' for k, v in pares) + "</div>")


def fila(principal: str, secundario: str, derecha: str, insignia: str = "") -> None:
    """Fila de lista: [insignia + monto] [motivo] [fecha]."""
    _html(
        f'<div class="sl-row"><div>{insignia}<div class="m" style="margin-top:6px">{escape(principal)}</div></div>'
        f'<div class="s">{escape(secundario)}</div><div class="f">{escape(derecha)}</div></div>'
    )


def echarts(opciones: dict, alto: int = 360, clave: str | None = None) -> None:
    """Dibuja una gráfica de ECharts (opciones armadas en viz/).

    El import va aquí adentro: streamlit_echarts solo funciona dentro de `streamlit run`
    (fuera de la app, por ejemplo en pytest, falla al importarse).
    """
    from streamlit_echarts import st_echarts

    st_echarts(options=opciones, height=f"{alto}px", key=clave)


def seccion(titulo: str) -> None:
    _html(f'<div class="sl-section">{escape(titulo)}</div>')


def cita(texto: str) -> None:
    _html(f'<div class="sl-quote">{escape(texto).replace(chr(10), "<br>")}</div>')
