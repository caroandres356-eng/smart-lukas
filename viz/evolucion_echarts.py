"""Gráfica del Panel · "Tus pesos durante el mes" (ECharts).

- Una línea escalonada por ruta con SU color; la elegida más gruesa y con degradado debajo.
- Línea punteada "Mínimo para tus gastos": lo que pide la política (gastos fijos acumulados a su fecha).
- Zona sombreada donde una ruta NO válida queda por debajo de ese mínimo (explica por qué no se eligió).
Datos: viz.evolucion.serie_pesos (operaciones del motor + tasa del motor), politica.gastos_fijos y Ruta.nota.
"""

from __future__ import annotations

from decimal import Decimal

from core.modelos import Cotizacion, Politica, Propuesta
from motor.rutas import DIAS_PERIODO, fecha_del_gasto
from viz import estilo
from viz.evolucion import MESES, serie_pesos


def minimo_gastos(politica: Politica, historico: list[Cotizacion]) -> list[Decimal | None]:
    """COP que ya deberías tener cada día para pagar los gastos fijos vencidos (None antes del primero)."""
    dia0 = historico[0].fecha
    fechas_gasto = [(fecha_del_gasto(g, dia0), g.monto_cop) for g in politica.gastos_fijos]
    salida: list[Decimal | None] = []
    for cot in historico[:DIAS_PERIODO]:
        vencidos = [m for f, m in fechas_gasto if f <= cot.fecha]
        salida.append(sum(vencidos, Decimal(0)) if vencidos else None)
    return salida


def opciones_evolucion(propuesta: Propuesta, historico: list[Cotizacion], politica: Politica) -> dict:
    periodo = historico[:DIAS_PERIODO]
    dia0 = periodo[0].fecha
    dias = [str((c.fecha - dia0).days + 1) for c in periodo]
    minimo = minimo_gastos(politica, historico)

    series: list[dict] = []
    leyenda: list[str] = []
    # Las no elegidas primero (quedan detrás); la elegida al final, encima.
    for ruta in sorted(propuesta.rutas, key=lambda r: r.nombre == propuesta.elegida):
        es_elegida = ruta.nombre == propuesta.elegida
        color = estilo.color_ruta(ruta.nombre)
        nombre = f"{estilo.LETRAS.get(ruta.nombre, '')} · {ruta.nombre}"
        valores = [v for _, v in serie_pesos(ruta, historico)]
        leyenda.append(nombre)
        linea = {
            "name": nombre,
            "type": "line",
            "step": "end",
            "data": [float(v) for v in valores],
            "showSymbol": False,
            "lineStyle": {"width": 3.5 if es_elegida else 2.5, "color": color},
            "itemStyle": {"color": color},
            "z": 5 if es_elegida else 3,
            "emphasis": {"focus": "series"},
        }
        if es_elegida:
            linea["areaStyle"] = {
                "color": {"type": "linear", "x": 0, "y": 0, "x2": 0, "y2": 1,
                          "colorStops": [{"offset": 0, "color": "rgba(46,125,50,0.22)"},
                                         {"offset": 1, "color": "rgba(46,125,50,0)"}]}
            }
            # Puntos en los días en que la elegida convierte a pesos.
            dias_conversion = {(o.fecha_programada - dia0).days for o in ruta.operaciones if o.hacia == "COP"}
            linea["markPoint"] = {
                "symbol": "circle",
                "symbolSize": 11,
                "itemStyle": {"color": color, "borderColor": "#ffffff", "borderWidth": 2.5},
                "label": {"show": False},
                "tooltip": {"show": False},
                "data": [{"coord": [dias[i], float(valores[i])]} for i in sorted(dias_conversion) if i < len(dias)],
            }
        series.append(linea)

        if not ruta.valida:
            # Zona de faltante: base invisible (la ruta) + diferencia hasta el mínimo, apiladas.
            pila = f"falta-{estilo.LETRAS.get(ruta.nombre, ruta.nombre)}"
            faltas = [
                float(m - v) if m is not None and v < m else 0.0 for m, v in zip(minimo, valores)
            ]
            if any(faltas):
                primer_dia = next(i for i, f in enumerate(faltas) if f)
                series.append({"type": "line", "step": "end", "stack": pila, "data": [float(v) for v in valores],
                               "lineStyle": {"opacity": 0}, "showSymbol": False, "silent": True,
                               "tooltip": {"show": False}, "z": 1})
                series.append({
                    "type": "line", "step": "end", "stack": pila, "data": faltas,
                    "lineStyle": {"opacity": 0}, "showSymbol": False, "silent": True, "tooltip": {"show": False},
                    "areaStyle": {"color": color, "opacity": 0.14}, "z": 1,
                    "markPoint": {
                        "symbol": "roundRect", "symbolSize": 1, "tooltip": {"show": False},
                        "data": [{"coord": [dias[primer_dia], float(valores[primer_dia])]}],
                        "label": {
                            "show": True, "position": "bottom", "distance": 14, "align": "left",
                            "formatter": f"{{t|{estilo.LETRAS.get(ruta.nombre, '')} no alcanza para tus gastos}}\n{{s|{ruta.nota or ''}}}",
                            "backgroundColor": "#ffffff", "borderColor": "#f2b8cf", "borderWidth": 1,
                            "borderRadius": 8, "padding": [7, 10],
                            "rich": {"t": {"fontWeight": 700, "color": "#9c2a5a", "fontSize": 12, "lineHeight": 17},
                                     "s": {"color": "#7a3352", "fontSize": 11, "lineHeight": 16}},
                        },
                    },
                })

    leyenda.append("Mínimo para tus gastos")
    series.append({
        "name": "Mínimo para tus gastos",
        "type": "line",
        "step": "end",
        "data": [float(m) if m is not None else None for m in minimo],
        "showSymbol": False,
        "lineStyle": {"type": "dashed", "width": 1.5, "color": estilo.TINTA_2},
        "itemStyle": {"color": estilo.TINTA_2},
        "z": 4,
    })

    nombre_mes = MESES[dia0.month - 1]
    return {
        "backgroundColor": "transparent",
        "textStyle": estilo.TEXTO_ECHARTS,
        "animationDuration": 1400,
        "grid": {"left": 64, "right": 24, "top": 72, "bottom": 46},
        "legend": {"data": leyenda, "top": 0, "left": 0, "icon": "roundRect", "itemWidth": 18, "itemHeight": 4,
                   "textStyle": {"color": estilo.TINTA_2, "fontSize": 12}},
        "tooltip": {
            **estilo.TOOLTIP_ECHARTS,
            "trigger": "axis",
            "axisPointer": {"type": "line", "lineStyle": {"color": "#9aa7a0"}},
            "valueFormatter": estilo.js(estilo.JS_PESOS),
        },
        "xAxis": {
            "type": "category", "data": dias, "boundaryGap": False,
            "name": f"Día de {nombre_mes}", "nameLocation": "middle", "nameGap": 30,
            "nameTextStyle": {"color": estilo.TINTA_2, "fontSize": 12},
            "axisLine": {"lineStyle": {"color": "#cfd8d3"}}, "axisTick": {"show": False},
            "axisLabel": {"color": estilo.TINTA_2, "interval": 6},
        },
        "yAxis": {
            "type": "value", "min": 0,
            "splitLine": {"lineStyle": {"color": "#eef1ef"}},
            "axisLabel": {"color": estilo.TINTA_2, "formatter": estilo.js(
                "function(v){return v===0?'$0':'$'+(v/1e6).toLocaleString('es-CO',{maximumFractionDigits:1})+' M';}")},
        },
        "series": series,
    }
