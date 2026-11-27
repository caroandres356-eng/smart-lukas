"""Contrato que CUALQUIER BancoPort debe cumplir.

Corre contra BancoFalso (debe pasar). Para BancoSimulado, BeloApiBanco y BeloMcpBanco
quitar el skip de su línea en ADAPTADORES cuando se implementen.
"""

from datetime import date
from decimal import Decimal

import pytest

from banco.belo_api import BeloApiBanco
from banco.belo_mcp import BeloMcpBanco
from banco.reloj import RelojSimulado
from banco.simulado import BancoSimulado
from core.modelos import Operacion
from core.puertos import BancoPort
from fakes.fakes import BancoFalso

ADAPTADORES = [
    pytest.param(BancoFalso, id="fakes"),
    pytest.param(
        lambda: BancoSimulado(RelojSimulado(date(2026, 11, 1))),
        id="simulado",
        marks=pytest.mark.skip(reason="Persona 1: pendiente BancoSimulado"),
    ),
    pytest.param(BeloApiBanco, id="belo_api", marks=pytest.mark.skip(reason="pendiente credenciales de Belo")),
    pytest.param(BeloMcpBanco, id="belo_mcp", marks=pytest.mark.skip(reason="pendiente credenciales de Belo")),
]


@pytest.fixture(params=ADAPTADORES)
def banco(request) -> BancoPort:
    return request.param()


def operacion_pequena(**cambios) -> Operacion:
    datos = dict(tipo="conversion", desde="USD", hacia="COP", monto=Decimal("10.00"), categoria="prueba", fecha_programada=date(2026, 11, 1))
    datos.update(cambios)
    return Operacion(**datos)


def test_cumple_el_protocolo(banco):
    assert isinstance(banco, BancoPort)


def test_saldos(banco):
    saldos = banco.saldos()
    monedas = {s.moneda for s in saldos}
    assert {"USD", "COP", "USDT"} <= monedas
    for s in saldos:
        assert isinstance(s.monto, Decimal)
        assert s.monto >= 0
        assert s.fuente in ("simulado", "belo")


def test_cotizacion_usd_cop(banco):
    c = banco.cotizacion("USD", "COP")
    assert c.desde == "USD" and c.hacia == "COP"
    assert isinstance(c.tasa, Decimal) and c.tasa > 0
    assert Decimal(0) <= c.spread < Decimal(1)


def test_rendimiento_usdt(banco):
    r = banco.rendimiento("USDT")
    assert r.moneda == "USDT"
    assert isinstance(r.tasa_anual, Decimal) and r.tasa_anual >= 0


def test_ejecutar_ok_y_queda_en_movimientos(banco):
    antes = len(banco.movimientos())
    res = banco.ejecutar(operacion_pequena())
    assert res.ok is True
    assert len(banco.movimientos()) > antes


def test_ejecutar_es_idempotente(banco):
    op = operacion_pequena()
    primero = banco.ejecutar(op)
    assert primero.ok is True and primero.operacion_id == op.id
    saldos = banco.saldos()
    movimientos = len(banco.movimientos())

    segundo = banco.ejecutar(op)

    assert segundo.ok is False
    assert segundo.operacion_id == op.id
    assert banco.saldos() == saldos
    assert len(banco.movimientos()) == movimientos


def test_ids_distintos_se_ejecutan_ambos(banco):
    assert banco.ejecutar(operacion_pequena()).ok
    assert banco.ejecutar(operacion_pequena()).ok
