"""Pruebas de las gráficas (Persona 3): datos de ejemplo de fakes/, sin Streamlit."""

import subprocess
import sys
from decimal import Decimal
from html import escape

import plotly.graph_objects as go
import pytest

from fakes import fakes
from motor.decisor import proponer
from motor.rutas import RUTA_A
from viz import estilo
from viz.evolucion import grafica_evolucion, serie_pesos
from viz.reparto import grafica_reparto
from viz.rutas import grafica_rutas


@pytest.fixture
def propuesta():
    return fakes.cargar_propuesta_ejemplo()


@pytest.fixture
def politica():
    return fakes.cargar_politica_ejemplo()


@pytest.fixture
def historico():
    return fakes.cargar_cotizaciones_ejemplo()


@pytest.fixture
def figuras(propuesta, politica, historico):
    return [
        grafica_rutas(propuesta),
        grafica_reparto(fakes.cargar_ingreso_ejemplo(), politica),
        grafica_evolucion(propuesta, historico, politica),
    ]


# --------------------------------------------------------------------------- generales


def test_viz_no_importa_streamlit():
    codigo = (
        "import sys; import viz.rutas, viz.reparto, viz.evolucion, viz.flujo, viz.evolucion_echarts, ui.calendario; "
        "sys.exit(1 if 'streamlit' in sys.modules else 0)"
    )
    assert subprocess.run([sys.executable, "-c", codigo]).returncode == 0


def test_todas_son_figuras_con_rotulo_de_datos_simulados(figuras):
    for fig in figuras:
        assert isinstance(fig, go.Figure)
        assert estilo.ROTULO_SIMULADO in fig.layout.title.text


def test_formato_de_pesos():
    assert estilo.pesos(Decimal("2612480")) == "$2.612.480"
    assert estilo.pesos_con_signo(Decimal("6949")) == "+$6.949"
    assert estilo.pesos_con_signo(Decimal("-1200")) == "-$1.200"
    assert estilo.pesos_con_signo(Decimal("0")) == "$0"


# --------------------------------------------------------------------------- rutas


def test_rutas_verde_solo_en_la_elegida(propuesta):
    barra = grafica_rutas(propuesta).data[0]
    assert len(barra.x) == 3
    colores = list(barra.marker.color)
    elegida = [r.nombre for r in propuesta.rutas].index(propuesta.elegida)
    assert colores[elegida] == estilo.VERDE
    assert colores.count(estilo.VERDE) == 1


def test_rutas_muestran_el_ahorro_del_motor(propuesta):
    fig = grafica_rutas(propuesta)
    barra = fig.data[0]
    elegida = [r.nombre for r in propuesta.rutas].index(propuesta.elegida)
    assert barra.x[elegida] == pytest.approx(float(propuesta.ahorro_cop))
    assert estilo.pesos(propuesta.ahorro_cop) in fig.layout.title.text
    assert barra.x[[r.nombre for r in propuesta.rutas].index(RUTA_A)] == 0


def test_rutas_con_la_propuesta_del_motor(politica):
    prop = proponer(fakes.cargar_ingreso_ejemplo(), fakes.BancoFalso(), fakes.MercadoFalso(), fakes.RelojFalso(), politica)
    fig = grafica_rutas(prop)
    assert estilo.pesos(prop.ahorro_cop) in fig.layout.title.text


# --------------------------------------------------------------------------- reparto


def test_reparto_150_200_650(politica):
    fig = grafica_reparto(fakes.cargar_ingreso_ejemplo(), politica)
    assert [t.name for t in fig.data] == ["Impuestos", "Colchón", "Disponible para decidir"]
    assert [t.x[0] for t in fig.data] == [150, 200, 650]
    assert fig.data[-1].marker.color == estilo.VERDE


# --------------------------------------------------------------------------- evolución


def test_evolucion_termina_en_cop_final_y_no_baja(propuesta, historico):
    for ruta in propuesta.rutas:
        serie = serie_pesos(ruta, historico)
        assert len(serie) == 30
        valores = [v for _, v in serie]
        assert valores == sorted(valores)
        assert abs(valores[-1] - ruta.cop_final) <= 1


def test_evolucion_una_linea_por_ruta_y_elegida_en_verde(propuesta, historico, politica):
    fig = grafica_evolucion(propuesta, historico, politica)
    lineas = [t for t in fig.data if t.mode == "lines"]
    assert len(lineas) == 3
    verdes = [t for t in lineas if t.line.color == estilo.VERDE]
    assert len(verdes) == 1 and propuesta.elegida in verdes[0].name


# --------------------------------------------------------------------------- Panel (ECharts y calendario)


@pytest.fixture
def propuesta_motor(politica):
    return proponer(fakes.cargar_ingreso_ejemplo(), fakes.BancoFalso(), fakes.MercadoFalso(), fakes.RelojFalso(), politica)


def test_flujo_cuadra_con_las_reservas_del_motor(propuesta_motor, politica):
    from motor.rutas import calcular_reservas
    from viz.flujo import destinos, opciones_flujo

    reservas = calcular_reservas(propuesta_motor.ingreso, politica)
    assert sum(m for m, _ in destinos(propuesta_motor).values()) == reservas.disponible_usd

    sankey = opciones_flujo(propuesta_motor, politica)["series"][0]
    desde_pago = sum(e["value"] for e in sankey["links"] if e["source"].startswith("Pago"))
    assert desde_pago == pytest.approx(float(propuesta_motor.ingreso.monto))


def test_minimo_para_gastos_sigue_la_politica(politica, historico):
    from viz.evolucion_echarts import minimo_gastos

    minimo = minimo_gastos(politica, historico)
    assert len(minimo) == 30
    assert minimo[0] is None  # antes del arriendo (día 5) no hay que pagar nada
    assert minimo[4] == Decimal("1800000")  # día 5: arriendo
    assert minimo[9] == Decimal("1920000")  # día 10: arriendo + internet


def test_evolucion_echarts_marca_el_faltante_de_la_ruta_no_valida(propuesta_motor, historico, politica):
    from viz.evolucion_echarts import opciones_evolucion

    opciones = opciones_evolucion(propuesta_motor, historico, politica)
    invalidas = [r for r in propuesta_motor.rutas if not r.valida]
    pilas = {s.get("stack") for s in opciones["series"] if s.get("stack")}
    assert pilas == {f"falta-{estilo.LETRAS[r.nombre]}" for r in invalidas}
    elegida = next(s for s in opciones["series"] if s.get("name", "").endswith(propuesta_motor.elegida))
    assert elegida["data"][-1] == pytest.approx(float(propuesta_motor.ruta_elegida().cop_final), abs=1)


def test_calendario_una_ficha_por_operacion(propuesta_motor, politica):
    from ui.calendario import html_calendario, resumen

    html = html_calendario(propuesta_motor, politica, propuesta_motor.ingreso.fecha)
    assert html.count("class='chip ") == len(propuesta_motor.veredictos)
    # Cada operación trae su nube de detalle (tooltip) con la regla aplicada.
    assert html.count("class='tip'") == len(propuesta_motor.veredictos)
    for v in propuesta_motor.veredictos:
        assert escape(v.motivo) in html
    assert html.count("class='evt'") == len(politica.gastos_fijos)
    conteo = resumen(propuesta_motor)
    assert conteo["auto"] + conteo["requiere_aprobacion"] + conteo["bloqueada"] == conteo["total"]


def test_momento_de_cada_operacion_segun_el_reloj(propuesta_motor):
    from datetime import timedelta

    from ui.calendario import momento

    dia_pago = propuesta_motor.ingreso.fecha
    arriendo = next(v for v in propuesta_motor.veredictos if v.estado == "requiere_aprobacion")
    automatica = next(v for v in propuesta_motor.veredictos if v.estado == "auto" and v.operacion.fecha_programada == dia_pago)
    assert momento(automatica, dia_pago) == ("hoy", "Hoy")
    assert momento(automatica, dia_pago - timedelta(days=1))[0] == "prog"
    assert momento(automatica, dia_pago + timedelta(days=1)) == ("hecha", "Hecha")
    # Sin permiso y con la fecha pasada, no se ejecuta (regla de la bandeja).
    assert momento(arriendo, dia_pago + timedelta(days=1))[0] == "nohecha"
