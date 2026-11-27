"""El contrato valida bien y los fixtures cargan en los modelos. DEBEN PASAR."""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from core.modelos import (
    CambioPolitica,
    GastoFijo,
    Operacion,
    Politica,
    Solicitud,
    nuevo_id,
)
from core.puertos import BancoPort, MercadoPort, Reloj
from fakes import fakes


def politica_valida(**cambios):
    datos = dict(
        auto_max_usd_por_operacion=Decimal(300),
        auto_max_usd_por_dia=Decimal(500),
        impuestos_pct=Decimal(15),
        colchon_usd=Decimal(200),
        gastos_fijos=[GastoFijo(nombre="arriendo", monto_cop=Decimal(1800000), dia=5)],
        vence_en_segundos=60,
        max_interrupciones_dia=3,
    )
    datos.update(cambios)
    return Politica(**datos)


# --------------------------------------------------------------------------- modelos


def test_nuevo_id_es_hex_de_12_y_unico():
    ids = {nuevo_id() for _ in range(200)}
    assert len(ids) == 200
    assert all(len(i) == 12 and int(i, 16) >= 0 for i in ids)


def test_operacion_id_por_defecto_unico_y_monto_decimal():
    a = Operacion(tipo="conversion", desde="USD", hacia="COP", monto="450.10", categoria="arriendo", fecha_programada=date(2026, 11, 1))
    b = Operacion(tipo="conversion", desde="USD", hacia="COP", monto="450.10", categoria="arriendo", fecha_programada=date(2026, 11, 1))
    assert a.id != b.id
    assert isinstance(a.monto, Decimal) and a.monto == Decimal("450.10")


def test_operacion_rechaza_moneda_invalida_y_monto_no_positivo():
    with pytest.raises(ValidationError):
        Operacion(tipo="conversion", desde="EUR", monto=1, categoria="x", fecha_programada=date(2026, 11, 1))
    with pytest.raises(ValidationError):
        Operacion(tipo="conversion", desde="USD", monto=0, categoria="x", fecha_programada=date(2026, 11, 1))


def test_politica_valida():
    p = politica_valida()
    assert p.reglas_aprendidas == []


@pytest.mark.parametrize(
    "campo,valor",
    [
        ("auto_max_usd_por_operacion", Decimal(-1)),
        ("auto_max_usd_por_dia", Decimal(-1)),
        ("colchon_usd", Decimal(-1)),
        ("impuestos_pct", Decimal(-1)),
        ("impuestos_pct", Decimal(101)),
        ("vence_en_segundos", -1),
        ("max_interrupciones_dia", -1),
    ],
)
def test_politica_rechaza_valores_invalidos(campo, valor):
    with pytest.raises(ValidationError):
        politica_valida(**{campo: valor})


def test_gasto_fijo_dia_entre_1_y_31():
    with pytest.raises(ValidationError):
        GastoFijo(nombre="x", monto_cop=Decimal(1), dia=0)
    with pytest.raises(ValidationError):
        GastoFijo(nombre="x", monto_cop=Decimal(1), dia=32)


def test_solicitud_fechas_quedan_en_utc():
    op = Operacion(tipo="pago", desde="COP", monto=1, categoria="x", fecha_programada=date(2026, 11, 1))
    s = Solicitud(operacion=op, motivo="m", creada=datetime(2026, 11, 1, 13, 0), vence=datetime(2026, 11, 1, 13, 1), estado="pendiente")
    assert s.creada.tzinfo == timezone.utc and s.vence.tzinfo == timezone.utc


def test_cambio_politica():
    c = CambioPolitica(accion="permitir_hasta", tipo="conversion", categoria="arriendo", monto_max_usd=Decimal(500))
    assert c.monto_max_usd == Decimal(500)
    with pytest.raises(ValidationError):
        CambioPolitica(accion="otra", tipo="conversion", categoria="arriendo")


# --------------------------------------------------------------------------- fixtures


def test_fixture_ingreso():
    ing = fakes.cargar_ingreso_ejemplo()
    assert ing.tipo == "ingreso" and ing.moneda == "USD" and ing.monto == Decimal(1000)


def test_fixture_cotizaciones_30_dias_alrededor_de_4000():
    cots = fakes.cargar_cotizaciones_ejemplo()
    assert len(cots) == 30
    assert all(c.desde == "USD" and c.hacia == "COP" and c.spread == Decimal("0.01") and c.fuente == "simulado" for c in cots)
    assert all(Decimal(3800) < c.tasa < Decimal(4300) for c in cots)
    assert [c.fecha for c in cots] == sorted(c.fecha for c in cots)


def test_fixture_rendimiento():
    r = fakes.cargar_rendimiento_ejemplo()
    assert r.moneda == "USDT" and r.tasa_anual == Decimal("0.10")


def test_fixture_propuesta_coherente():
    p = fakes.cargar_propuesta_ejemplo()
    nombres = [r.nombre for r in p.rutas]
    assert nombres == ["Todo hoy", "Lo justo hoy, el resto rindiendo", "Mitad y mitad"]
    assert p.elegida == "Lo justo hoy, el resto rindiendo"
    assert p.ruta_elegida().cop_final == max(r.cop_final for r in p.rutas)
    todo_hoy = next(r for r in p.rutas if r.nombre == "Todo hoy")
    assert p.ahorro_cop == p.ruta_elegida().cop_final - todo_hoy.cop_final
    arriendo = next(v for v in p.veredictos if v.operacion.categoria == "arriendo")
    assert arriendo.estado == "requiere_aprobacion"
    assert arriendo.operacion.monto == Decimal(450) and "300" in arriendo.motivo
    tramos = [v for v in p.veredictos if v.operacion.desde == "USDT"]
    assert len(tramos) == 4 and all(v.estado == "auto" for v in tramos)


def test_fixture_solicitudes():
    sols = fakes.cargar_solicitudes_ejemplo()
    assert sorted(s.estado for s in sols) == ["en_cola", "pendiente", "vencida"]
    pendiente = next(s for s in sols if s.estado == "pendiente")
    assert pendiente.operacion.monto == Decimal(450)
    assert (pendiente.vence - pendiente.creada).total_seconds() == 60


def test_politica_yaml_carga_en_el_modelo():
    p = fakes.cargar_politica_ejemplo()
    assert p.auto_max_usd_por_operacion == 300 and p.auto_max_usd_por_dia == 500
    assert p.impuestos_pct == 15 and p.colchon_usd == 200
    assert {g.nombre: (g.monto_cop, g.dia) for g in p.gastos_fijos} == {"arriendo": (1800000, 5), "internet": (120000, 10)}
    assert p.vence_en_segundos == 60 and p.max_interrupciones_dia == 3 and p.reglas_aprendidas == []


def test_fakes_cumplen_los_puertos():
    assert isinstance(fakes.BancoFalso(), BancoPort)
    assert isinstance(fakes.MercadoFalso(), MercadoPort)
    assert isinstance(fakes.RelojFalso(), Reloj)


def test_reloj_falso_avanza():
    r = fakes.RelojFalso()
    antes = r.ahora()
    r.avanzar_segundos(61)
    assert (r.ahora() - antes).total_seconds() == 61
    r.avanzar(7)
    assert (r.hoy() - antes.date()).days == 7
