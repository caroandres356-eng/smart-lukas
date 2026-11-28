"""Calendario del mes con las operaciones del agente (Persona 3).

Cada ficha es un veredicto de la propuesta (fecha, monto, de → a, estado y motivo en el tooltip).
Los días de pago de gastos fijos salen de la política. No se calcula nada: solo se ubica cada cosa en su día.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, timedelta
from html import escape

from core.modelos import Politica, Propuesta, Veredicto
from motor.rutas import fecha_del_gasto, fmt_cop, fmt_usd

DIAS_SEMANA = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
CLASE = {"auto": "ok", "requiere_aprobacion": "warn", "bloqueada": "bad"}
NOMBRES = {
    "impuestos": "Impuestos",
    "rendimiento": "A rendir en USDT",
    "resto": "Resto a pesos",
    "mitad": "Mitad a pesos",
}


def _texto(v: Veredicto, tramo: int | None, total_tramos: int) -> str:
    op = v.operacion
    if op.categoria == "escalonado" and tramo is not None:
        base = f"Tramo {tramo} de {total_tramos}" + (" · con intereses" if tramo == total_tramos else "")
    else:
        base = NOMBRES.get(op.categoria, op.categoria.capitalize())
    if v.estado == "requiere_aprobacion":
        return f"{base} · espera tu permiso"
    if v.estado == "bloqueada":
        return f"{base} · bloqueada"
    return base


def resumen(propuesta: Propuesta) -> dict[str, int]:
    conteo = {"total": len(propuesta.veredictos), "auto": 0, "requiere_aprobacion": 0, "bloqueada": 0}
    for v in propuesta.veredictos:
        conteo[v.estado] += 1
    return conteo


def html_calendario(propuesta: Propuesta, politica: Politica, hoy: date) -> str:
    """HTML del calendario del mes del pago."""
    inicio = propuesta.ingreso.fecha
    anio, mes = inicio.year, inicio.month
    por_dia: dict[date, list[Veredicto]] = defaultdict(list)
    for v in propuesta.veredictos:
        por_dia[v.operacion.fecha_programada].append(v)

    tramos = sorted(v.operacion.fecha_programada for v in propuesta.veredictos if v.operacion.categoria == "escalonado")
    numero_tramo = {f: i + 1 for i, f in enumerate(tramos)}

    gastos: dict[date, list[str]] = defaultdict(list)
    for g in politica.gastos_fijos:
        f = fecha_del_gasto(g, inicio)
        gastos[f].append(f"<div class='evt'>Pagas {escape(g.nombre)}<b>${fmt_cop(g.monto_cop)}</b>"
                         f"<span>ya convertido antes</span></div>")

    # Las columnas (días de la semana) donde hay operaciones van más anchas, para que las fichas respiren.
    columnas_hl = {d.weekday() for d in por_dia}
    plantilla = " ".join("minmax(0,2.3fr)" if i in columnas_hl else "minmax(0,1fr)" for i in range(7))
    partes = [f"<div class='sl-cal-wrap'><div class='sl-cal' style='grid-template-columns:{plantilla}'>"]
    partes += [f"<div class='wd{' hl' if i in columnas_hl else ''}'>{d}</div>" for i, d in enumerate(DIAS_SEMANA)]

    primero = date(anio, mes, 1)
    ultimo = date(anio, mes, calendar.monthrange(anio, mes)[1])
    dia = primero - timedelta(days=primero.weekday())
    fin = ultimo + timedelta(days=6 - ultimo.weekday())
    while dia <= fin:
        if dia.month != mes:
            partes.append(f"<div class='day out'><div class='dn'>{dia.day}</div></div>")
        else:
            ops = por_dia.get(dia, [])
            clases = "day" + (" hot" if ops else "") + (" today" if dia == hoy else "")
            cab = f"<div class='dn'>{dia.day}</div>"
            if dia == hoy or dia == inicio:
                etiqueta = "Hoy · llega el pago" if dia == inicio == hoy else ("Hoy" if dia == hoy else "Llega el pago")
                cab = f"<div class='dh'><span class='dn'>{dia.day}</span><span class='tag'>{etiqueta}</span></div>"
            fichas = []
            for v in ops:
                op = v.operacion
                texto = _texto(v, numero_tramo.get(op.fecha_programada), len(tramos))
                fichas.append(
                    f"<div class='chip {CLASE[v.estado]}' title='{escape(v.motivo, quote=True)}'><i class='dot'></i>"
                    f"<div><b>{fmt_usd(op.monto)} {op.desde} → {op.hacia or ''}</b><span>{escape(texto)}</span></div></div>"
                )
            partes.append(f"<div class='{clases}'>{cab}{''.join(fichas)}{''.join(gastos.get(dia, []))}</div>")
        dia += timedelta(days=1)
    partes.append("</div></div>")
    return "".join(partes)
