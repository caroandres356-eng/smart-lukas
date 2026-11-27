"""Comportamiento esperado de la bandeja (Persona 3) con el caso de demo.

Quitar el @pytest.mark.skip de cada test a medida que se implemente.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from aprobaciones.bandeja import Bandeja
from core.modelos import Operacion
from fakes.fakes import RelojFalso

PENDIENTE = pytest.mark.skip(reason="Persona 3: pendiente")


@pytest.fixture
def reloj():
    return RelojFalso()


@pytest.fixture
def bandeja(reloj):
    return Bandeja(reloj, vence_en_segundos=60, max_interrupciones_dia=3)


def op(monto=450, categoria="arriendo") -> Operacion:
    return Operacion(tipo="conversion", desde="USD", hacia="COP", monto=Decimal(monto), categoria=categoria, fecha_programada=date(2026, 11, 1))


@PENDIENTE
def test_crear_solicitud_queda_pendiente_y_vence_en_60s(bandeja, reloj):
    s = bandeja.crear_solicitud(op(), "450 USD supera el límite de 300 USD por operación")
    assert s.estado == "pendiente"
    assert s.creada == reloj.ahora()
    assert s.vence == reloj.ahora() + timedelta(seconds=60)
    assert bandeja.pendientes() == [s]


@PENDIENTE
def test_cuarta_solicitud_del_dia_queda_en_cola(bandeja):
    for i in range(3):
        assert bandeja.crear_solicitud(op(400 + i), "m").estado == "pendiente"
    cuarta = bandeja.crear_solicitud(op(500), "m")
    assert cuarta.estado == "en_cola"
    assert bandeja.en_cola() == [cuarta]


@PENDIENTE
def test_a_los_61s_vence_y_no_se_ejecuta(bandeja, reloj):
    s = bandeja.crear_solicitud(op(), "m")
    reloj.avanzar_segundos(61)
    vencidas = bandeja.actualizar_vencidas()
    assert [v.id for v in vencidas] == [s.id]
    assert bandeja.historial()[0].estado == "vencida"
    assert bandeja.pendientes() == []


@PENDIENTE
def test_antes_de_60s_sigue_pendiente(bandeja, reloj):
    bandeja.crear_solicitud(op(), "m")
    reloj.avanzar_segundos(59)
    assert bandeja.actualizar_vencidas() == []
    assert len(bandeja.pendientes()) == 1


@PENDIENTE
def test_solo_esta_vez_aprueba_sin_cambiar_politica(bandeja):
    s = bandeja.crear_solicitud(op(), "m")
    assert bandeja.responder(s.id, "solo_esta_vez") is None
    assert bandeja.historial()[0].estado == "aprobada"


@PENDIENTE
def test_siempre_aprueba_y_aprende_hasta_la_siguiente_centena(bandeja):
    s = bandeja.crear_solicitud(op(450), "m")
    cambio = bandeja.responder(s.id, "siempre")
    assert bandeja.historial()[0].estado == "aprobada"
    assert cambio.accion == "permitir_hasta"
    assert cambio.tipo == "conversion" and cambio.categoria == "arriendo"
    assert cambio.monto_max_usd == Decimal(500)


@PENDIENTE
def test_nunca_rechaza_y_aprende_a_bloquear(bandeja):
    s = bandeja.crear_solicitud(op(320, "viaje"), "m")
    cambio = bandeja.responder(s.id, "nunca")
    assert bandeja.historial()[0].estado == "rechazada"
    assert cambio.accion == "bloquear" and cambio.categoria == "viaje"


@PENDIENTE
def test_no_se_puede_responder_una_vencida(bandeja, reloj):
    s = bandeja.crear_solicitud(op(), "m")
    reloj.avanzar_segundos(61)
    bandeja.actualizar_vencidas()
    with pytest.raises(ValueError):
        bandeja.responder(s.id, "solo_esta_vez")


@PENDIENTE
def test_al_dia_siguiente_se_reinician_las_interrupciones(bandeja, reloj):
    for _ in range(3):
        bandeja.crear_solicitud(op(), "m")
    reloj.avanzar(1)
    assert bandeja.crear_solicitud(op(), "m").estado == "pendiente"
