"""Pantalla de inicio: Panel (dashboard). Sigue la maqueta aprobada por Cristian.

Todo sale de estado.propuesta() (motor), la política y el banco/mercado; aquí solo se presenta.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from html import escape

import streamlit as st

from fakes import fakes
from motor.rutas import RUTA_A
from ui import bandeja, calendario, estado
from ui import componentes as c
from viz.estilo import LETRAS, color_ruta
from viz.evolucion import MESES, serie_pesos
from viz.evolucion_echarts import opciones_evolucion
from viz.flujo import opciones_flujo

ICONO_CHAT = (
    "<svg width='20' height='20' viewBox='0 0 24 24' fill='none' stroke='#9fd8a6' stroke-width='2' "
    "stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
    "<path d='M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z'></path></svg>"
)


def _html(texto: str) -> None:
    st.markdown(texto, unsafe_allow_html=True)


def _titulo(titulo: str, subtitulo: str) -> None:
    _html(f"<div class='sl-ct'><h2>{escape(titulo)}</h2><p>{escape(subtitulo)}</p></div>")


def _sparkline(valores: list[Decimal], color: str) -> str:
    """Mini tendencia escalonada en SVG (solo dibuja la serie que ya viene del motor)."""
    if not valores:
        return ""
    bajo, alto = min(valores), max(valores)
    rango = (alto - bajo) or Decimal(1)
    n = len(valores) - 1 or 1
    puntos = []
    for i, v in enumerate(valores):
        x = 200 * i / n
        y = 28 - float((v - bajo) / rango) * 26
        puntos.append(f"{x:.1f},{y:.1f}")
    return (f"<svg width='100%' height='30' viewBox='0 0 200 30' preserveAspectRatio='none' aria-hidden='true' "
            f"style='display:block;margin-top:6px'><polyline points='{' '.join(puntos)}' fill='none' "
            f"stroke='{color}' stroke-width='2' stroke-linejoin='round'/></svg>")


def _kpis(prop, conteo, historico) -> None:
    elegida = prop.ruta_elegida()
    todo_hoy = next((r for r in prop.rutas if r.nombre == RUTA_A), elegida)
    porcentaje = (prop.ahorro_cop / todo_hoy.cop_final * 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    serie = [v for _, v in serie_pesos(elegida, historico)]
    ing = prop.ingreso
    _html(
        "<div class='sl-kpis'>"
        f"<div class='sl-kpi'><div class='k'>Llegó</div>"
        f"<div class='v'>{c.fmt_usd(ing.monto)} <small>{ing.moneda}</small></div>"
        f"<div class='d'>{c.fecha_corta(ing.fecha)} · {escape(ing.descripcion)}</div></div>"
        f"<div class='sl-kpi on'><div class='k'>Ganas frente a «Todo hoy»<span class='tag'>{str(porcentaje).replace('.', ',')} %</span></div>"
        f"<div class='v'>{c.pesos_con_signo(prop.ahorro_cop)}</div>{_sparkline(serie, color_ruta(elegida.nombre))}</div>"
        f"<div class='sl-kpi'><div class='k'>Pesos al cierre del mes</div>"
        f"<div class='v'>{c.pesos(elegida.cop_final)}</div>"
        f"<div class='d'>Con «Todo hoy» serían {c.pesos(todo_hoy.cop_final)}</div></div>"
        f"<div class='sl-kpi{' warn' if conteo['requiere_aprobacion'] else ''}'><div class='k'>Esperando tu permiso</div>"
        f"<div class='v'>{conteo['requiere_aprobacion']} <small>{'operación' if conteo['requiere_aprobacion'] == 1 else 'operaciones'}</small></div>"
        f"<div class='d'>{conteo['auto']} se hacen solas · {conteo['bloqueada']} bloqueadas</div></div>"
        "</div>"
    )


def _solicitudes() -> tuple[list, bool]:
    """(solicitudes, son_de_ejemplo). Sin los avisos grandes de estado.intentar: en el Panel basta una nota."""
    b = st.session_state["bandeja"]
    try:
        b.actualizar_vencidas()
    except NotImplementedError:
        pass
    try:
        return b.historial(), False
    except NotImplementedError:
        return fakes.cargar_solicitudes_ejemplo(), True


def _bandeja() -> None:
    reloj = st.session_state["reloj"]
    pol = estado.politica()
    solicitudes, de_ejemplo = _solicitudes()
    pendientes = [s for s in solicitudes if s.estado == "pendiente"]

    cab_izq, cab_der = st.columns([1, 1], vertical_alignment="center")
    cab_izq.markdown("<div class='sl-ct'><h2>Bandeja</h2></div>", unsafe_allow_html=True)
    if not pendientes:
        st.caption("No hay nada esperando tu permiso. El agente sigue solo dentro de tus reglas.")
        return
    cab_der.markdown(f"<div style='text-align:right'>{c.insignia_estado('requiere_aprobacion')}</div>", unsafe_allow_html=True)

    sol = pendientes[0]
    op = sol.operacion
    quedan = max(int((sol.vence - reloj.ahora()).total_seconds()), 0)
    _html(
        f"<div style='font-size:2rem;font-weight:800;letter-spacing:-.02em;margin-top:4px'>{c.dolares(op.monto)}</div>"
        f"<div style='color:#4d5a53;font-size:.9rem'>a {escape(op.hacia or '')} para <b style='color:#17201b'>{escape(op.categoria)}</b></div>"
        f"<div style='background:#f7f9f8;border:1px solid #e2e8e4;border-radius:12px;padding:11px 13px;margin:12px 0;"
        f"font-size:.88rem;color:#33403a;line-height:1.5'>{escape(sol.motivo)}</div>"
        f"<div style='display:flex;justify-content:space-between;font-size:.82rem;color:#4d5a53'>"
        f"<span>Vence en</span><b style='color:#7a4a00'>{quedan} s</b></div>"
    )
    st.progress(min(quedan / max(pol.vence_en_segundos, 1), 1.0))
    st.caption("Si no respondes, no se ejecuta nada.")
    if st.button("Aprobar solo esta vez", key=f"panel-{sol.id}-una", type="primary", width="stretch",
                 help=bandeja.AYUDAS["solo_esta_vez"]):
        bandeja._responder(sol.id, "solo_esta_vez")
    b1, b2 = st.columns(2)
    if b1.button("Siempre en este rango", key=f"panel-{sol.id}-siempre", width="stretch", help=bandeja.AYUDAS["siempre"]):
        bandeja._responder(sol.id, "siempre")
    if b2.button("Nunca", key=f"panel-{sol.id}-nunca", width="stretch", help=bandeja.AYUDAS["nunca"]):
        bandeja._responder(sol.id, "nunca")
    otros = {e: sum(1 for s in solicitudes if s.estado == e) for e in ("en_cola", "vencida")}
    extras = []
    if len(pendientes) > 1:
        extras.append(f"{len(pendientes) - 1} pendientes más")
    if otros["en_cola"]:
        extras.append(f"{otros['en_cola']} en cola")
    if otros["vencida"]:
        extras.append(f"{otros['vencida']} vencida{'s' if otros['vencida'] > 1 else ''} · no se ejecutó")
    if extras:
        _html("<div class='sl-chips' style='margin-top:10px'>" + "".join(f"<span class='sl-chip'>{escape(t)}</span>" for t in extras) + "</div>")
    if de_ejemplo:
        st.caption("Solicitudes de ejemplo: la bandeja (aprobaciones/) aún no está conectada.")


def al_cierre(prop) -> str:
    todo_hoy = next((r for r in prop.rutas if r.nombre == RUTA_A), None)
    base = todo_hoy.cop_final if todo_hoy else Decimal(0)
    maximo = max((r.cop_final - base for r in prop.rutas), default=Decimal(1)) or Decimal(1)
    partes = ["<div class='sl-cierre'><div class='h'>Al cierre del mes</div>"]
    for r in sorted(prop.rutas, key=lambda r: r.cop_final, reverse=True):
        color = color_ruta(r.nombre)
        es_elegida = r.nombre == prop.elegida
        estado_txt = "elegida" if es_elegida else ("no cubre gastos" if not r.valida else r.nombre)
        if r.nombre == RUTA_A:
            barra = "<div class='b'>punto de comparación</div>"
        else:
            dif = r.cop_final - base
            ancho = max(float(dif / maximo * 100), 2) if dif > 0 else 2
            barra = (f"<div class='b'><div style='width:{ancho:.0f}%;background:{color}'></div>"
                     f"<b style='color:{'#1f5f24' if es_elegida else '#4d5a53'}'>{c.pesos_con_signo(dif)}</b></div>")
        partes.append(
            f"<div class='it'><div class='l'><span style='background:{color}'></span><b>{LETRAS.get(r.nombre, '')}</b> · {escape(estado_txt)}</div>"
            f"<div class='v' style='{'' if es_elegida else 'font-size:1.05rem;color:#33403a'}'>{c.pesos(r.cop_final)}</div>{barra}</div>"
        )
    partes.append("<div style='font-size:.72rem;color:#4d5a53;line-height:1.45'>Las barras amplían la diferencia frente a "
                  "«Todo hoy»: al final las líneas casi se tocan.</div></div>")
    return "".join(partes)


def _rutas(prop) -> None:
    _titulo("Las 3 rutas", "Pesos de más frente a convertir todo hoy")
    todo_hoy = next((r for r in prop.rutas if r.nombre == RUTA_A), None)
    partes = []
    for r in prop.rutas:
        color = color_ruta(r.nombre)
        nombre = f"<b><i class='pt' style='background:{color}'></i>{LETRAS.get(r.nombre, '')} · {escape(r.nombre)}</b>"
        if r.nombre == prop.elegida:
            partes.append(
                f"<div class='sl-ruta on'><div class='t'>{nombre}{c.pill('Elegida', 'ok')}</div>"
                f"<div class='bar'><div><div style='width:100%;background:{color}'></div></div>"
                f"<b style='color:#1f5f24'>{c.pesos_con_signo(prop.ahorro_cop)}</b></div></div>"
            )
        elif not r.valida:
            partes.append(f"<div class='sl-ruta off'><div class='t'>{nombre}{c.pill('No cubre gastos', 'bad')}</div>"
                          f"<div class='n'>{escape(r.nota or '')}</div></div>")
        elif r.nombre == RUTA_A or todo_hoy is None:
            partes.append(f"<div class='sl-ruta'><div class='t'>{nombre}<span style='color:#4d5a53'>{c.pesos(r.cop_final)}</span></div>"
                          f"<div class='n'>Punto de comparación</div></div>")
        else:
            partes.append(f"<div class='sl-ruta'><div class='t'>{nombre}<span>{c.pesos_con_signo(r.cop_final - todo_hoy.cop_final)}</span></div></div>")
    _html("".join(partes))


def render() -> None:
    prop = estado.propuesta()
    pol = estado.politica()
    reloj = st.session_state["reloj"]
    historico = st.session_state["mercado"].historico("USD", "COP", 30)
    conteo = calendario.resumen(prop)
    mes = MESES[prop.ingreso.fecha.month - 1]
    letra = LETRAS.get(prop.elegida, "")

    pendiente_txt = (f"{conteo['requiere_aprobacion']} operación espera tu permiso." if conteo["requiere_aprobacion"] == 1
                     else f"{conteo['requiere_aprobacion']} operaciones esperan tu permiso." if conteo["requiere_aprobacion"]
                     else "Todo está dentro de tus reglas.")
    _html(
        f"<div class='sl-hola'><div><div class='s'>Hola · {c.pill('● Datos simulados', 'sim')}</div>"
        f"<h1>Tu pago de {mes} ya tiene plan</h1></div>"
        f"<div class='r'>El agente eligió la ruta <b>{letra} · {escape(prop.elegida)}</b>. {pendiente_txt}</div></div>"
    )
    _kpis(prop, conteo, historico)

    izq, der = st.columns([2, 1], gap="medium")
    with izq.container(border=True, key="card_flujo"):
        _titulo("Así se reparte tu pago",
                "Del pago se apartan impuestos y colchón; del disponible, hoy se convierte lo justo para tus gastos.")
        c.echarts(opciones_flujo(prop, pol), alto=330, clave="flujo")
    with der.container(border=True, key="card_bandeja"):
        _bandeja()

    izq, der = st.columns([2, 1], gap="medium")
    with izq.container(border=True, key="card_evolucion"):
        _titulo(f"Tus pesos durante {mes}",
                f"La ruta {letra} convierte lo que necesitas para tus gastos y deja el resto rindiendo.")
        graf, cierre = st.columns([3, 1], gap="small")
        with graf:
            c.echarts(opciones_evolucion(prop, historico, pol), alto=360, clave="evolucion")
        with cierre:
            _html(al_cierre(prop))
    with der.container(border=True, key="card_rutas"):
        _rutas(prop)

    with st.container(border=True, key="card_calendario"):
        izq, der = st.columns([3, 2], vertical_alignment="top")
        with izq:
            _titulo(f"Tu mes con el agente · {mes} {prop.ingreso.fecha.year}",
                    f"Las {conteo['total']} operaciones del plan, en el día en que pasan. Pasa el cursor por una operación para ver su detalle.")
        with der:
            _html("<div class='sl-leyenda' style='justify-content:flex-end;margin-top:6px'>"
                  "<span><i style='background:#2e7d32'></i>Automática</span>"
                  "<span><i style='background:#fff;border:2.5px solid #c98a1b;box-sizing:border-box'></i>Requiere tu permiso</span>"
                  "<span><i style='background:#b3261e;border-radius:2px'></i>Bloqueada</span>"
                  "<span><i style='background:#f1f3f2;border:1px solid #c9d1cd;border-radius:3px'></i>Pago de un gasto fijo</span></div>")
        _html(
            "<div class='sl-stats'>"
            f"<div><div class='n'>{conteo['total']}</div><div class='t'>operaciones en el mes</div></div>"
            f"<div class='ok'><div class='n'>{conteo['auto']}</div><div class='t'>se hacen solas</div></div>"
            f"<div class='warn'><div class='n'>{conteo['requiere_aprobacion']}</div><div class='t'>esperan tu permiso</div></div>"
            "<div class='txt'>El día del pago se separan las reservas y se convierte lo de los gastos fijos; "
            "luego, cada semana, sale un tramo del USDT a pesos.</div></div>"
        )
        _html(calendario.html_calendario(prop, pol, reloj.hoy()))

    from motor.explicador import explicar

    texto = estado.intentar(explicar, prop)
    if texto:
        _html(f"<div class='sl-explica'><div class='ic'>{ICONO_CHAT}</div><div style='flex:1;min-width:0'>"
              f"<div class='h'>En palabras simples</div><p>{escape(texto)}</p></div></div>")
