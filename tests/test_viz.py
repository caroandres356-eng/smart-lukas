"""Pruebas de las gráficas (Persona 3): datos de ejemplo de fakes/, sin Streamlit."""

import subprocess
import sys
from decimal import Decimal

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
        "import sys; import viz.rutas, viz.reparto, viz.evolucion; "
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
