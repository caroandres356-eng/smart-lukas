"""Comportamiento esperado del motor (Persona 2) con el caso de demo de Laura.

Quitar el @pytest.mark.skip de cada test a medida que se implemente.
"""

import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

import pytest

from core.modelos import CambioPolitica, Cotizacion, Movimiento, Operacion
from fakes import fakes

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


def test_450_requiere_aprobacion_y_menciona_300(politica):
    from motor.decisor import evaluar

    v = evaluar(conversion(450), politica, acumulado_dia_usd=Decimal(0), saldo_usd=Decimal(850))
    assert v.estado == "requiere_aprobacion"
    assert "300" in v.motivo and "450" in v.motivo


def test_permitir_hasta_500_arriendo_vuelve_auto(politica):
    from motor.decisor import evaluar
    from motor.politica import aplicar_cambio

    p = aplicar_cambio(politica, CambioPolitica(accion="permitir_hasta", tipo="conversion", categoria="arriendo", monto_max_usd=Decimal(500)))
    v = evaluar(conversion(450), p, acumulado_dia_usd=Decimal(0), saldo_usd=Decimal(850))
    assert v.estado == "auto"
    assert "500" in v.motivo


def test_permitir_hasta_no_aplica_si_el_monto_no_cabe(politica):
    from motor.decisor import evaluar
    from motor.politica import aplicar_cambio

    p = aplicar_cambio(politica, CambioPolitica(accion="permitir_hasta", tipo="conversion", categoria="arriendo", monto_max_usd=Decimal(400)))
    assert evaluar(conversion(450), p, Decimal(0), Decimal(850)).estado == "requiere_aprobacion"


def test_regla_bloquear_gana_a_todo(politica):
    from motor.decisor import evaluar
    from motor.politica import aplicar_cambio

    p = aplicar_cambio(politica, CambioPolitica(accion="bloquear", tipo="conversion", categoria="viaje"))
    v = evaluar(conversion(10, categoria="viaje"), p, Decimal(0), Decimal(850))
    assert v.estado == "bloqueada"


def test_colchon_bloquea(politica):
    from motor.decisor import evaluar

    v = evaluar(conversion(250, categoria="ahorro"), politica, Decimal(0), saldo_usd=Decimal(400))
    assert v.estado == "bloqueada"
    assert "200" in v.motivo and "150" in v.motivo


def test_limite_diario_pide_aprobacion(politica):
    from motor.decisor import evaluar

    v = evaluar(conversion(100, categoria="ahorro"), politica, acumulado_dia_usd=Decimal(480), saldo_usd=Decimal(850))
    assert v.estado == "requiere_aprobacion"
    assert "500" in v.motivo


def test_operacion_pequena_es_auto(politica):
    from motor.decisor import evaluar

    v = evaluar(conversion(30, categoria="internet"), politica, Decimal(0), Decimal(850))
    assert v.estado == "auto"
    assert v.motivo


def test_usd_a_usdt_es_movimiento_interno(politica):
    from motor.decisor import evaluar

    op = Operacion(tipo="conversion", desde="USD", hacia="USDT", monto=Decimal(900), categoria="impuestos", fecha_programada=HOY)
    v = evaluar(op, politica, acumulado_dia_usd=Decimal(499), saldo_usd=Decimal(100))
    assert v.estado == "auto"
    assert v.motivo == "Movimiento interno entre tus saldos; no cuenta para tus límites"


def test_bloquear_gana_a_permitir_hasta(politica):
    from motor.decisor import evaluar

    p = politica.model_copy(update={"reglas_aprendidas": [
        CambioPolitica(accion="bloquear", tipo="conversion", categoria="arriendo"),
        CambioPolitica(accion="permitir_hasta", tipo="conversion", categoria="arriendo", monto_max_usd=Decimal(500)),
    ]})
    v = evaluar(conversion(10), p, Decimal(0), Decimal(850))
    assert v.estado == "bloqueada" and "arriendo" in v.motivo


def test_colchon_va_antes_que_el_limite_por_operacion(politica):
    from motor.decisor import evaluar

    v = evaluar(conversion("454.55"), politica, Decimal(0), saldo_usd=Decimal(600))
    assert v.estado == "bloqueada"
    assert v.motivo == "Te dejaría 145,45 USD, por debajo de tu colchón de 200 USD"


def test_motivo_por_operacion_con_decimales(politica):
    from motor.decisor import evaluar

    v = evaluar(conversion("454.55"), politica, Decimal(0), Decimal(850))
    assert v.motivo == "454,55 USD supera tu límite de 300 USD por operación"


def test_motivo_limite_diario_con_numeros(politica):
    from motor.decisor import evaluar

    v = evaluar(conversion(200, categoria="resto"), politica, acumulado_dia_usd=Decimal(450), saldo_usd=Decimal(850))
    assert v.motivo == "Con esta operación hoy llevarías 650 USD y tu límite diario es 500 USD"


def test_usdt_a_cop_cuenta_para_limites_pero_no_para_el_colchon(politica):
    from motor.decisor import evaluar

    v = evaluar(conversion(50, categoria="escalonado", desde="USDT"), politica, Decimal(0), saldo_usd=Decimal(0))
    assert v.estado == "auto"
    v = evaluar(conversion(350, categoria="escalonado", desde="USDT"), politica, Decimal(0), saldo_usd=Decimal(0))
    assert v.estado == "requiere_aprobacion"


# --------------------------------------------------------------------------- rutas y propuesta


def historico_sintetico(tasas, spread="0.01", inicio=HOY):
    """Histórico con las tasas dadas, un día por elemento, empezando en `inicio`."""
    return [
        Cotizacion(desde="USD", hacia="COP", tasa=Decimal(t), spread=Decimal(spread), fecha=inicio + timedelta(days=i), fuente="simulado")
        for i, t in enumerate(tasas)
    ]


def ingreso(monto="1000", fecha=HOY) -> Movimiento:
    return Movimiento(fecha=fecha, tipo="ingreso", moneda="USD", monto=Decimal(monto))


def rutas_por_nombre(rutas):
    return {r.nombre: r for r in rutas}


CONSTANTE = historico_sintetico([4000] * 30)
SUBIENDO = historico_sintetico([4000 + 10 * d for d in range(30)])


def test_reservas_y_disponible(politica):
    from motor.rutas import calcular_reservas

    r = calcular_reservas(ingreso(), politica)
    assert (r.impuestos_usd, r.colchon_usd, r.disponible_usd) == (Decimal(150), Decimal(200), Decimal(650))


def test_usd_para_el_arriendo_redondea_hacia_arriba(politica):
    from motor.rutas import usd_para_gasto

    arriendo = next(g for g in politica.gastos_fijos if g.nombre == "arriendo")
    # 1.800.000 / (4.000 × 0,99) = 454,5454... -> 454,55
    assert usd_para_gasto(arriendo, CONSTANTE[0]) == Decimal("454.55")


def test_todo_hoy_con_tasa_constante_es_650_por_3960(politica):
    from motor.rutas import calcular_rutas

    a = calcular_rutas(ingreso(), CONSTANTE, fakes.cargar_rendimiento_ejemplo(), politica)[0]
    assert a.nombre == "Todo hoy"
    assert a.cop_final == Decimal(650) * Decimal(3960)
    assert [o.categoria for o in a.operaciones] == ["arriendo", "internet", "resto"]
    assert sum(o.monto for o in a.operaciones) == Decimal(650)


def test_mitad_y_mitad_es_invalida_por_el_arriendo(politica):
    from motor.rutas import calcular_rutas

    c = rutas_por_nombre(calcular_rutas(ingreso(), CONSTANTE, fakes.cargar_rendimiento_ejemplo(), politica))["Mitad y mitad"]
    assert c.valida is False
    # 325 USD × 3.960 = 1.287.000 COP; faltan 1.800.000 − 1.287.000 = 513.000
    assert c.nota == "No alcanza para el arriendo del día 5: faltan 513.000 COP"


def test_con_los_datos_de_la_demo_c_es_invalida_y_a_b_validas(politica):
    from motor.rutas import calcular_rutas

    rutas = rutas_por_nombre(
        calcular_rutas(fakes.cargar_ingreso_ejemplo(), fakes.cargar_cotizaciones_ejemplo(), fakes.cargar_rendimiento_ejemplo(), politica)
    )
    assert rutas["Todo hoy"].valida and rutas["Lo justo hoy, el resto rindiendo"].valida
    assert not rutas["Mitad y mitad"].valida and "arriendo" in rutas["Mitad y mitad"].nota


def test_ruta_b_operaciones(politica):
    from motor.rutas import calcular_rutas

    b = calcular_rutas(ingreso(), CONSTANTE, fakes.cargar_rendimiento_ejemplo(), politica)[1]
    ops = b.operaciones
    assert [(o.desde, o.hacia, o.categoria) for o in ops[:3]] == [
        ("USD", "COP", "arriendo"), ("USD", "COP", "internet"), ("USD", "USDT", "rendimiento")
    ]
    tramos = ops[3:]
    assert [o.fecha_programada for o in tramos] == [HOY + timedelta(days=d) for d in (7, 14, 21, 28)]
    assert all(o.desde == "USDT" and o.categoria == "escalonado" for o in tramos)
    assert tramos[0].monto == tramos[1].monto == tramos[2].monto
    assert tramos[3].monto > tramos[0].monto  # el último lleva el interés
    assert sum(o.monto for o in tramos) > ops[2].monto


def _ganancia_b_sobre_a(historico, politica):
    from motor.rutas import calcular_rutas

    rutas = rutas_por_nombre(calcular_rutas(ingreso(), historico, fakes.cargar_rendimiento_ejemplo(), politica))
    return rutas["Lo justo hoy, el resto rindiendo"], rutas["Todo hoy"]


def test_con_tasa_constante_b_gana_solo_por_el_rendimiento(politica):
    b, a = _ganancia_b_sobre_a(CONSTANTE, politica)
    usdt_entra = next(o.monto for o in b.operaciones if o.hacia == "USDT")
    usdt_sale = sum(o.monto for o in b.operaciones if o.desde == "USDT")
    interes = usdt_sale - usdt_entra
    assert interes > 0
    assert b.cop_final - a.cop_final == (interes * Decimal(3960)).quantize(Decimal(1))


def test_con_tasa_subiendo_b_gana_por_mas(politica):
    b_c, a_c = _ganancia_b_sobre_a(CONSTANTE, politica)
    b_s, a_s = _ganancia_b_sobre_a(SUBIENDO, politica)
    assert b_s.cop_final - a_s.cop_final > b_c.cop_final - a_c.cop_final > 0


def test_calcular_rutas_con_fixtures(politica):
    """A y C coinciden con fixtures/propuesta.json (±1 COP). B NO: el fixture usa otra regla
    (USD enteros para los gastos y tramos saldo/restantes). B se verificó a mano: 2.612.508."""
    from motor.rutas import calcular_rutas

    esperada = rutas_por_nombre(fakes.cargar_propuesta_ejemplo().rutas)
    rutas = calcular_rutas(
        fakes.cargar_ingreso_ejemplo(), fakes.cargar_cotizaciones_ejemplo(), fakes.cargar_rendimiento_ejemplo(), politica
    )
    assert [r.nombre for r in rutas] == ["Todo hoy", "Lo justo hoy, el resto rindiendo", "Mitad y mitad"]
    calc = rutas_por_nombre(rutas)
    for nombre in ("Todo hoy", "Mitad y mitad"):
        assert abs(calc[nombre].cop_final - esperada[nombre].cop_final) <= Decimal(1)
    assert calc["Lo justo hoy, el resto rindiendo"].cop_final == Decimal(2612508)


def test_todo_hoy_es_disponible_por_trm1_menos_spread(politica):
    from motor.rutas import calcular_rutas

    cots = fakes.cargar_cotizaciones_ejemplo()
    rutas = calcular_rutas(fakes.cargar_ingreso_ejemplo(), cots, fakes.cargar_rendimiento_ejemplo(), politica)
    disponible = Decimal(1000) - Decimal(150) - Decimal(200)
    esperado = (disponible * cots[0].tasa * (1 - cots[0].spread)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    assert rutas[0].cop_final == esperado


def test_ninguna_ruta_toca_reservas(politica):
    from motor.rutas import calcular_rutas

    rutas = calcular_rutas(
        fakes.cargar_ingreso_ejemplo(), fakes.cargar_cotizaciones_ejemplo(), fakes.cargar_rendimiento_ejemplo(), politica
    )
    for r in rutas:
        usd_que_sale = sum(o.monto for o in r.operaciones if o.desde == "USD")
        assert usd_que_sale == Decimal(650)  # todo el disponible, nada de las reservas
        assert all(o.categoria != "impuestos" for o in r.operaciones)


def test_proponer_elige_lo_justo_hoy_y_calcula_ahorro(politica):
    from motor.decisor import proponer

    p = proponer(fakes.cargar_ingreso_ejemplo(), fakes.BancoFalso(), fakes.MercadoFalso(), fakes.RelojFalso(), politica)
    assert p.elegida == "Lo justo hoy, el resto rindiendo"
    todo_hoy = next(r for r in p.rutas if r.nombre == "Todo hoy")
    assert p.ahorro_cop == p.ruta_elegida().cop_final - todo_hoy.cop_final
    assert p.ahorro_cop > 0
    arriendo = next(v for v in p.veredictos if v.operacion.categoria == "arriendo")
    assert arriendo.estado == "requiere_aprobacion"


def _propuesta(politica):
    from motor.decisor import proponer

    return proponer(fakes.cargar_ingreso_ejemplo(), fakes.BancoFalso(), fakes.MercadoFalso(), fakes.RelojFalso(), politica)


def test_proponer_arriendo_pide_aprobacion_y_menciona_300(politica):
    p = _propuesta(politica)
    arriendo = next(v for v in p.veredictos if v.operacion.categoria == "arriendo")
    assert arriendo.estado == "requiere_aprobacion"
    assert "300" in arriendo.motivo


def test_proponer_tras_permitir_hasta_500_arriendo_es_auto(politica):
    from motor.politica import aplicar_cambio

    p = _propuesta(aplicar_cambio(politica, CambioPolitica(accion="permitir_hasta", tipo="conversion", categoria="arriendo", monto_max_usd=Decimal(500))))
    assert next(v for v in p.veredictos if v.operacion.categoria == "arriendo").estado == "auto"


def test_proponer_con_regla_bloquear_arriendo_queda_bloqueada(politica):
    from motor.politica import aplicar_cambio

    p = _propuesta(aplicar_cambio(politica, CambioPolitica(accion="bloquear", tipo="conversion", categoria="arriendo")))
    assert next(v for v in p.veredictos if v.operacion.categoria == "arriendo").estado == "bloqueada"


def test_proponer_ahorro_es_b_menos_a_y_no_elige_invalidas(politica):
    p = _propuesta(politica)
    rutas = {r.nombre: r for r in p.rutas}
    assert p.ahorro_cop == rutas["Lo justo hoy, el resto rindiendo"].cop_final - rutas["Todo hoy"].cop_final
    assert p.ahorro_cop == Decimal(2612508 - 2605532)
    assert rutas["Mitad y mitad"].valida is False


def test_proponer_evalua_impuestos_primero_y_en_orden_de_fecha(politica):
    p = _propuesta(politica)
    primero = p.veredictos[0]
    assert primero.operacion.categoria == "impuestos" and primero.operacion.monto == Decimal(150)
    assert primero.estado == "auto"
    fechas = [v.operacion.fecha_programada for v in p.veredictos]
    assert fechas == sorted(fechas)
    # Ninguna operación de la demo toca el colchón: 1.000 − 150 − 650 = 200
    assert all(v.estado != "bloqueada" for v in p.veredictos)


# --------------------------------------------------------------------------- explicador


@pytest.fixture
def sin_ia(monkeypatch):
    monkeypatch.delenv("IA_PROVEEDOR", raising=False)
    monkeypatch.delenv("IA_API_KEY", raising=False)


def test_explicar_dice_que_por_que_y_cuanto(sin_ia):
    from motor.explicador import explicar

    p = fakes.cargar_propuesta_ejemplo()
    texto = explicar(p)
    assert isinstance(texto, str) and texto
    assert "6.949" in texto  # el ahorro, sin cambiar el monto
    assert "450" in texto  # la operación que necesita aprobación


def test_explicar_propuesta_real_tiene_ingreso_ruta_y_ahorro(sin_ia, politica):
    from motor.explicador import explicar

    texto = explicar(_propuesta(politica))
    assert "1.000 USD" in texto
    assert "Lo justo hoy, el resto rindiendo" in texto
    assert "6.976" in texto  # 2.612.508 − 2.605.532
    assert "449,05" in texto and "300" in texto  # lo que necesita aprobación y por qué
    assert "150 USD" in texto and "200 USD" in texto  # impuestos y colchón
    frases = [f for f in re.split(r"(?<=[.!?])\s+", texto) if f]
    assert 4 <= len(frases) <= 6


def test_sin_llave_de_ia_devuelve_la_plantilla(monkeypatch):
    from motor import explicador

    monkeypatch.setenv("IA_PROVEEDOR", "gemini")
    monkeypatch.delenv("IA_API_KEY", raising=False)
    llamada = lambda *a: pytest.fail("no debe llamar a la IA sin llave")  # noqa: E731
    monkeypatch.setattr(explicador, "_pedir_a_ia", llamada)
    p = fakes.cargar_propuesta_ejemplo()
    assert explicador.explicar(p) == explicador.plantilla(p)


def test_ia_que_cambia_un_numero_se_descarta(monkeypatch):
    from motor import explicador

    monkeypatch.setenv("IA_PROVEEDOR", "groq")
    monkeypatch.setenv("IA_API_KEY", "llave-de-prueba")
    p = fakes.cargar_propuesta_ejemplo()
    original = explicador.plantilla(p)
    monkeypatch.setattr(explicador, "_pedir_a_ia", lambda *a: original.replace("6.949", "7.000"))
    assert explicador.explicar(p) == original


def test_ia_que_respeta_los_numeros_se_usa(monkeypatch):
    from motor import explicador

    monkeypatch.setenv("IA_PROVEEDOR", "gemini")
    monkeypatch.setenv("IA_API_KEY", "llave-de-prueba")
    p = fakes.cargar_propuesta_ejemplo()
    original = explicador.plantilla(p)
    monkeypatch.setattr(explicador, "_pedir_a_ia", lambda *a: "¡Hola! " + original)
    assert explicador.explicar(p) == "¡Hola! " + original


def test_si_la_ia_falla_devuelve_la_plantilla(monkeypatch):
    from motor import explicador

    monkeypatch.setenv("IA_PROVEEDOR", "gemini")
    monkeypatch.setenv("IA_API_KEY", "llave-de-prueba")

    def falla(*a):
        raise TimeoutError("tardó más de 5 s")

    monkeypatch.setattr(explicador, "_pedir_a_ia", falla)
    p = fakes.cargar_propuesta_ejemplo()
    assert explicador.explicar(p) == explicador.plantilla(p)


# --------------------------------------------------------------------------- backtest


def _backtest(tasas, politica, meses=12):
    from motor.backtest import backtest

    return backtest(Decimal(1000), historico_sintetico(tasas, inicio=date(2026, 1, 1)), fakes.cargar_rendimiento_ejemplo(), politica, meses)


def test_backtest_tendencia_plana_gana_b_por_el_rendimiento(politica):
    r = _backtest([4000] * 360, politica)
    assert r.meses_calculados == 12 and r.nota is None
    assert r.victorias["Lo justo hoy, el resto rindiendo"] == 12
    assert r.ahorro_promedio_cop > 0


def test_backtest_tendencia_subiendo_nunca_gana_todo_hoy(politica):
    r = _backtest([4000 + 3 * d for d in range(360)], politica)
    assert r.victorias["Todo hoy"] == 0
    assert all(m.ahorro_cop > 0 for m in r.meses)


def test_backtest_tendencia_bajando_gana_todo_hoy(politica):
    r = _backtest([4500 - 5 * d for d in range(360)], politica)
    assert r.victorias["Todo hoy"] == 12
    assert r.ahorro_promedio_cop == 0


def test_backtest_historico_corto_usa_los_meses_que_alcanzan(politica):
    r = _backtest([4000] * 100, politica)
    assert r.meses_calculados == 3 and len(r.meses) == 3
    assert "3 de 12" in r.nota
    assert [m.desde for m in r.meses] == [date(2026, 1, 1), date(2026, 1, 31), date(2026, 3, 2)]
