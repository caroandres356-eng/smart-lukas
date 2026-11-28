"""Pruebas del análisis (Persona 3): escenarios del dólar y punto de equilibrio, siempre con el motor."""

import subprocess
import sys
from decimal import Decimal

import plotly.graph_objects as go
import pytest

from analisis.escenarios import escenarios, historico_escenario, punto_equilibrio
from fakes import fakes
from motor.rutas import RUTA_A, RUTA_B, calcular_rutas
from viz import estilo
from viz.escenarios import grafica_escenarios


@pytest.fixture
def datos():
    return (fakes.cargar_ingreso_ejemplo(), fakes.cargar_cotizaciones_ejemplo(),
            fakes.cargar_rendimiento_ejemplo(), fakes.cargar_politica_ejemplo())


def test_historico_escenario_no_cambia_el_dia_del_pago_y_llega_a_la_variacion(datos):
    _, historico, _, _ = datos
    sube = historico_escenario(historico, Decimal("3"))
    assert sube[0].tasa == historico[0].tasa  # el dólar de hoy ya se conoce
    assert sube[-1].tasa == (historico[29].tasa * Decimal("1.03")).quantize(Decimal("0.01"))
    assert [c.fecha for c in sube] == [c.fecha for c in historico[:30]]
    assert historico_escenario(historico, Decimal("0")) == historico[:30]


def test_escenario_igual_es_exactamente_el_motor(datos):
    ingreso, historico, rendimiento, politica = datos
    igual = escenarios(ingreso, historico, rendimiento, politica, Decimal("3"))[1]
    assert igual.nombre == "igual"
    # Las operaciones tienen ids aleatorios: se comparan los resultados, no los ids.
    resumen = lambda rutas: [(r.nombre, r.cop_final, r.valida, r.nota) for r in rutas]  # noqa: E731
    assert resumen(igual.rutas) == resumen(calcular_rutas(ingreso, historico, rendimiento, politica))


def test_si_el_dolar_sube_b_gana_mas_y_todo_hoy_no_cambia(datos):
    ingreso, historico, rendimiento, politica = datos
    baja, igual, sube = escenarios(ingreso, historico, rendimiento, politica, Decimal("3"))
    for nombre in (RUTA_B,):
        assert baja.ruta(nombre).cop_final < igual.ruta(nombre).cop_final < sube.ruta(nombre).cop_final
    # «Todo hoy» convierte el día del pago, que no cambia en ningún escenario.
    assert baja.ruta(RUTA_A).cop_final == igual.ruta(RUTA_A).cop_final == sube.ruta(RUTA_A).cop_final


def test_punto_de_equilibrio_es_donde_todo_hoy_alcanza_a_la_elegida(datos):
    ingreso, historico, rendimiento, politica = datos
    eq = punto_equilibrio(ingreso, historico, rendimiento, politica, RUTA_B)
    assert eq is not None and Decimal(0) < eq < Decimal(20)

    def ventaja(bajada):
        rutas = {r.nombre: r for r in calcular_rutas(ingreso, historico_escenario(historico, -bajada), rendimiento, politica)}
        return rutas[RUTA_B].cop_final - rutas[RUTA_A].cop_final

    assert ventaja(eq - Decimal("0.05")) > 0  # un poco antes del equilibrio, B todavía gana
    assert ventaja(eq + Decimal("0.05")) <= 0  # un poco después, ya no
    assert punto_equilibrio(ingreso, historico, rendimiento, politica, RUTA_A) is None


def test_grafica_de_escenarios(datos):
    ingreso, historico, rendimiento, politica = datos
    escs = escenarios(ingreso, historico, rendimiento, politica, Decimal("3"))
    eq = punto_equilibrio(ingreso, historico, rendimiento, politica, RUTA_B)
    fig = grafica_escenarios(escs, RUTA_B, eq)
    assert isinstance(fig, go.Figure)
    assert estilo.ROTULO_SIMULADO in fig.layout.title.text
    assert "no es una promesa" in fig.layout.title.text
    assert [t.marker.color for t in fig.data] == [estilo.color_ruta(r.nombre) for r in escs[0].rutas if r.nombre != RUTA_A]
    b = next(t for t in fig.data if RUTA_B in t.name)
    assert b.y[1] == pytest.approx(float(escs[1].ruta(RUTA_B).cop_final - escs[1].ruta(RUTA_A).cop_final))


def test_analisis_no_importa_streamlit():
    codigo = "import sys; import analisis.escenarios, viz.escenarios; sys.exit(1 if 'streamlit' in sys.modules else 0)"
    assert subprocess.run([sys.executable, "-c", codigo]).returncode == 0
