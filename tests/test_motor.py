"""Comportamiento esperado del motor (Persona 2) con el caso de demo de Laura.

Quitar el @pytest.mark.skip de cada test a medida que se implemente.
"""

from datetime import date
from decimal import Decimal

import pytest

from core.modelos import CambioPolitica, Operacion
from fakes import fakes

PENDIENTE = pytest.mark.skip(reason="Persona 2: pendiente")
HOY = date(2026, 11, 1)


@pytest.fixture
def politica():
    return fakes.cargar_politica_ejemplo()


def conversion(monto, categoria="arriendo", desde="USD") -> Operacion:
    return Operacion(tipo="conversion", desde=desde, hacia="COP", monto=Decimal(monto), categoria=categoria, fecha_programada=HOY)


# --------------------------------------------------------------------------- política


def test_cargar_politica_por_defecto():
    from motor.politica import cargar_politica

    p = cargar_politica()
    assert p.auto_max_usd_por_operacion == 300
    assert p.colchon_usd == 200
    assert len(p.gastos_fijos) == 2


def test_guardar_y_cargar_ida_y_vuelta(tmp_path, politica):
    from motor.politica import cargar_politica, guardar_politica

    ruta = tmp_path / "politica.yaml"
    guardar_politica(politica, ruta)
    assert cargar_politica(ruta) == politica


def test_aplicar_cambio_no_muta_la_original(politica):
    from motor.politica import aplicar_cambio

    cambio = CambioPolitica(accion="permitir_hasta", tipo="conversion", categoria="arriendo", monto_max_usd=Decimal(500))
    nueva = aplicar_cambio(politica, cambio)
    assert nueva.reglas_aprendidas == [cambio]
    assert politica.reglas_aprendidas == []


def test_politica_con_impuestos_negativos_falla(tmp_path):
    from motor.politica import PoliticaInvalida, cargar_politica

    ruta = tmp_path / "mala.yaml"
    texto = (fakes.RUTA_POLITICA).read_text(encoding="utf-8").replace("impuestos_pct: 15", "impuestos_pct: -5")
    ruta.write_text(texto, encoding="utf-8")
    with pytest.raises(PoliticaInvalida, match="impuestos_pct"):
        cargar_politica(ruta)


def test_politica_sin_un_campo_falla_con_mensaje_claro(tmp_path):
    from motor.politica import PoliticaInvalida, cargar_politica

    ruta = tmp_path / "incompleta.yaml"
    lineas = fakes.RUTA_POLITICA.read_text(encoding="utf-8").splitlines()
    ruta.write_text("\n".join(l for l in lineas if not l.startswith("colchon_usd")), encoding="utf-8")
    with pytest.raises(PoliticaInvalida, match="falta el campo 'colchon_usd'"):
        cargar_politica(ruta)


def test_aplicar_cambio_dos_veces_misma_categoria_deja_una_regla(politica):
    from motor.politica import aplicar_cambio

    p = aplicar_cambio(politica, CambioPolitica(accion="permitir_hasta", tipo="conversion", categoria="arriendo", monto_max_usd=Decimal(500)))
    p = aplicar_cambio(p, CambioPolitica(accion="permitir_hasta", tipo="conversion", categoria="arriendo", monto_max_usd=Decimal(600)))
    p = aplicar_cambio(p, CambioPolitica(accion="bloquear", tipo="conversion", categoria="viaje"))
    arriendo = [r for r in p.reglas_aprendidas if r.categoria == "arriendo"]
    assert len(arriendo) == 1 and arriendo[0].monto_max_usd == 600
    assert len(p.reglas_aprendidas) == 2


# --------------------------------------------------------------------------- decisor (6 reglas)


@PENDIENTE
def test_450_requiere_aprobacion_y_menciona_300(politica):
    from motor.decisor import evaluar

    v = evaluar(conversion(450), politica, acumulado_dia_usd=Decimal(0), saldo_usd=Decimal(850))
    assert v.estado == "requiere_aprobacion"
    assert "300" in v.motivo and "450" in v.motivo


@PENDIENTE
def test_permitir_hasta_500_arriendo_vuelve_auto(politica):
    from motor.decisor import evaluar
    from motor.politica import aplicar_cambio

    p = aplicar_cambio(politica, CambioPolitica(accion="permitir_hasta", tipo="conversion", categoria="arriendo", monto_max_usd=Decimal(500)))
    v = evaluar(conversion(450), p, acumulado_dia_usd=Decimal(0), saldo_usd=Decimal(850))
    assert v.estado == "auto"
    assert "500" in v.motivo


@PENDIENTE
def test_permitir_hasta_no_aplica_si_el_monto_no_cabe(politica):
    from motor.decisor import evaluar
    from motor.politica import aplicar_cambio

    p = aplicar_cambio(politica, CambioPolitica(accion="permitir_hasta", tipo="conversion", categoria="arriendo", monto_max_usd=Decimal(400)))
    assert evaluar(conversion(450), p, Decimal(0), Decimal(850)).estado == "requiere_aprobacion"


@PENDIENTE
def test_regla_bloquear_gana_a_todo(politica):
    from motor.decisor import evaluar
    from motor.politica import aplicar_cambio

    p = aplicar_cambio(politica, CambioPolitica(accion="bloquear", tipo="conversion", categoria="viaje"))
    v = evaluar(conversion(10, categoria="viaje"), p, Decimal(0), Decimal(850))
    assert v.estado == "bloqueada"


@PENDIENTE
def test_colchon_bloquea(politica):
    from motor.decisor import evaluar

    v = evaluar(conversion(250, categoria="ahorro"), politica, Decimal(0), saldo_usd=Decimal(400))
    assert v.estado == "bloqueada"
    assert "200" in v.motivo and "150" in v.motivo


@PENDIENTE
def test_limite_diario_pide_aprobacion(politica):
    from motor.decisor import evaluar

    v = evaluar(conversion(100, categoria="ahorro"), politica, acumulado_dia_usd=Decimal(480), saldo_usd=Decimal(850))
    assert v.estado == "requiere_aprobacion"
    assert "500" in v.motivo


@PENDIENTE
def test_operacion_pequena_es_auto(politica):
    from motor.decisor import evaluar

    v = evaluar(conversion(30, categoria="internet"), politica, Decimal(0), Decimal(850))
    assert v.estado == "auto"
    assert v.motivo


# --------------------------------------------------------------------------- rutas y propuesta


@PENDIENTE
def test_calcular_rutas_con_fixtures(politica):
    from motor.rutas import calcular_rutas

    esperada = fakes.cargar_propuesta_ejemplo()
    rutas = calcular_rutas(
        fakes.cargar_ingreso_ejemplo(), fakes.cargar_cotizaciones_ejemplo(), fakes.cargar_rendimiento_ejemplo(), politica
    )
    assert [r.nombre for r in rutas] == ["Todo hoy", "Lo justo hoy, el resto rindiendo", "Mitad y mitad"]
    for calculada, fixture in zip(rutas, esperada.rutas):
        assert abs(calculada.cop_final - fixture.cop_final) <= Decimal(1)


@PENDIENTE
def test_todo_hoy_es_disponible_por_trm1_menos_spread(politica):
    from motor.rutas import calcular_rutas

    cots = fakes.cargar_cotizaciones_ejemplo()
    rutas = calcular_rutas(fakes.cargar_ingreso_ejemplo(), cots, fakes.cargar_rendimiento_ejemplo(), politica)
    disponible = Decimal(1000) - Decimal(150) - Decimal(200)
    assert rutas[0].cop_final == (disponible * cots[0].tasa * (1 - cots[0].spread)).quantize(Decimal("0.01"))


@PENDIENTE
def test_ninguna_ruta_toca_reservas(politica):
    from motor.rutas import calcular_rutas

    rutas = calcular_rutas(
        fakes.cargar_ingreso_ejemplo(), fakes.cargar_cotizaciones_ejemplo(), fakes.cargar_rendimiento_ejemplo(), politica
    )
    for r in rutas:
        usd_que_sale = sum(o.monto for o in r.operaciones if o.desde == "USD")
        assert usd_que_sale <= Decimal(650)


@PENDIENTE
def test_proponer_elige_lo_justo_hoy_y_calcula_ahorro(politica):
    from motor.decisor import proponer

    p = proponer(fakes.cargar_ingreso_ejemplo(), fakes.BancoFalso(), fakes.MercadoFalso(), fakes.RelojFalso(), politica)
    assert p.elegida == "Lo justo hoy, el resto rindiendo"
    todo_hoy = next(r for r in p.rutas if r.nombre == "Todo hoy")
    assert p.ahorro_cop == p.ruta_elegida().cop_final - todo_hoy.cop_final
    assert p.ahorro_cop > 0
    arriendo = next(v for v in p.veredictos if v.operacion.categoria == "arriendo")
    assert arriendo.estado == "requiere_aprobacion"


# --------------------------------------------------------------------------- explicador


@PENDIENTE
def test_explicar_dice_que_por_que_y_cuanto():
    from motor.explicador import explicar

    p = fakes.cargar_propuesta_ejemplo()
    texto = explicar(p)
    assert isinstance(texto, str) and texto
    assert "6.949" in texto  # el ahorro, sin cambiar el monto
    assert "450" in texto  # la operación que necesita aprobación
