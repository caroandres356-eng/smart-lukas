"""Gráfica del Panel · "Así se reparte tu pago" (Sankey de ECharts).

Pago → Impuestos / Colchón / Disponible → destinos de la ruta elegida.
No calcula nada nuevo:
- reservas: motor.rutas.calcular_reservas
- destinos: las operaciones que salen de USD en la ruta elegida (Ruta.operaciones), sumadas por categoría.
Devuelve el dict de opciones de ECharts; ui/ lo dibuja con componentes.echarts().
"""

from __future__ import annotations

from collections import OrderedDict
from decimal import Decimal

from core.modelos import Politica, Propuesta
from motor.rutas import calcular_reservas
from viz import estilo

NOMBRES = {
    "arriendo": "Arriendo",
    "internet": "Internet",
    "resto": "Resto a pesos",
    "rendimiento": "Rindiendo en USDT",
    "mitad": "A pesos en dos partes",
}


def destinos(propuesta: Propuesta) -> "OrderedDict[str, tuple[Decimal, str]]":
    """{nombre visible: (USD, moneda destino)} de lo que sale de USD en la ruta elegida, en orden de aparición."""
    salida: OrderedDict[str, tuple[Decimal, str]] = OrderedDict()
    for op in propuesta.ruta_elegida().operaciones:
        if op.desde != "USD":
            continue  # los tramos USDT → COP salen de lo que ya está rindiendo
        nombre = NOMBRES.get(op.categoria, op.categoria.capitalize())
        monto, _ = salida.get(nombre, (Decimal(0), op.hacia or ""))
        salida[nombre] = (monto + op.monto, op.hacia or "")
    return salida


def opciones_flujo(propuesta: Propuesta, politica: Politica) -> dict:
    reservas = calcular_reservas(propuesta.ingreso, politica)
    pago = f"Pago · {estilo.dolares(propuesta.ingreso.monto)}"
    impuestos = f"Impuestos · {estilo.dolares(reservas.impuestos_usd)}"
    colchon = f"Colchón · {estilo.dolares(reservas.colchon_usd)}"
    disponible = f"Disponible · {estilo.dolares(reservas.disponible_usd)}"

    nodos = [
        {"name": pago, "itemStyle": {"color": estilo.TINTA}, "depth": 0,
         "label": {"position": "left", "backgroundColor": "transparent", "fontWeight": 700}},
        {"name": impuestos, "itemStyle": {"color": "#6b7871"}, "depth": 1},
        {"name": colchon, "itemStyle": {"color": "#a9b4ae"}, "depth": 1},
        {"name": disponible, "itemStyle": {"color": estilo.VERDE}, "depth": 1,
         "label": {"fontWeight": 700, "color": "#1f5f24"}},
    ]
    enlaces = [
        {"source": pago, "target": impuestos, "value": float(reservas.impuestos_usd),
         "lineStyle": {"color": "#8f9b95", "opacity": 0.3}},
        {"source": pago, "target": colchon, "value": float(reservas.colchon_usd),
         "lineStyle": {"color": "#b9c3be", "opacity": 0.35}},
        {"source": pago, "target": disponible, "value": float(reservas.disponible_usd),
         "lineStyle": {"color": estilo.VERDE, "opacity": 0.22}},
    ]
    for nombre, (monto, hacia) in destinos(propuesta).items():
        color = estilo.TEAL if hacia == "USDT" else estilo.VERDE
        etiqueta = f"{nombre} · {estilo.dolares(monto)}"
        nodos.append({"name": etiqueta, "itemStyle": {"color": color}, "depth": 2})
        enlaces.append({"source": disponible, "target": etiqueta, "value": float(monto),
                        "lineStyle": {"color": color, "opacity": 0.3}})

    return {
        "backgroundColor": "transparent",
        "textStyle": estilo.TEXTO_ECHARTS,
        "tooltip": {
            **estilo.TOOLTIP_ECHARTS,
            "trigger": "item",
            "formatter": estilo.js(
                "function(p){var f=function(v){return Number(v).toLocaleString('es-CO',{maximumFractionDigits:2})+' USD';};"
                "if(p.dataType==='edge'){return p.data.source.split(' · ')[0]+' → '+p.data.target.split(' · ')[0]+'<br><b>'+f(p.data.value)+'</b>';}"
                "return '<b>'+p.name+'</b>';}"
            ),
        },
        "series": [
            {
                "type": "sankey",
                "left": 120,
                "right": 210,
                "top": 12,
                "bottom": 12,
                "nodeWidth": 14,
                "nodeGap": 22,
                "nodeAlign": "left",
                "layoutIterations": 0,  # respeta el orden en que se declaran los nodos
                "draggable": False,
                "emphasis": {"focus": "adjacency"},
                "itemStyle": {"borderWidth": 0, "borderRadius": 3},
                "lineStyle": {"curveness": 0.5},
                # Fondo blanco suave detrás de cada etiqueta para que se lea sobre las bandas.
                "label": {"color": estilo.TINTA, "fontFamily": estilo.FUENTE, "fontSize": 13, "fontWeight": 600,
                          "backgroundColor": "rgba(255,255,255,0.88)", "padding": [3, 6], "borderRadius": 6},
                "data": nodos,
                "links": enlaces,
                "animationDuration": 1200,
            }
        ],
    }
