"""Tests unitarios de `BancoSimulado` y `banco/fabrica.py`."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pytest

from banco import fabrica
from banco.mandatos import FirmadorMandatosAP2, PaymentMandate
from banco.mercado import MercadoSocrata
from banco.registro import Registro
from banco.reloj import RelojSimulado
from banco.simulado import BancoSimulado
from core.modelos import Cotizacion, Moneda, Operacion
from core.puertos import BancoPort, MercadoPort


class _MercadoStub:
    """Implementación mínima de MercadoPort (solo `historico`) para pruebas deterministas."""

    def __init__(self, cotizaciones: list[Cotizacion]) -> None:
        self._cotizaciones = cotizaciones

    def historico(self, desde: Moneda, hacia: Moneda, dias: int) -> list[Cotizacion]:
        filtradas = [c for c in self._cotizaciones if c.desde == desde and c.hacia == hacia]
        return filtradas[-dias:] if dias > 0 else []


def _cotizaciones_prueba() -> list[Cotizacion]:
    return [
        Cotizacion(
            desde="USD",
            hacia="COP",
            tasa=Decimal("4100.00"),
            spread=Decimal("0.01"),
            fecha=date(2026, 11, 1),
            fuente="simulado",
        ),
        Cotizacion(
            desde="USD",
            hacia="COP",
            tasa=Decimal("4200.50"),
            spread=Decimal("0.01"),
            fecha=date(2026, 11, 5),
            fuente="simulado",
        ),
    ]


def _saldos_por_moneda(banco: BancoSimulado) -> dict[Moneda, Decimal]:
    return {s.moneda: s.monto for s in banco.saldos()}


def test_formula_exacta_conversion_usd_y_usdt_a_cop() -> None:
    reloj = RelojSimulado(date(2026, 11, 1))
    mercado = _MercadoStub(_cotizaciones_prueba())
    assert isinstance(mercado, MercadoPort)

    banco = BancoSimulado(
        reloj=reloj,
        mercado=mercado,
        saldos_iniciales={
            "USD": Decimal("500.00"),
            "COP": Decimal("0.00"),
            "USDT": Decimal("200.00"),
        },
    )

    cot_usd = banco.cotizacion("USD", "COP")
    assert cot_usd.tasa == Decimal("4100.00")
    assert cot_usd.spread == Decimal("0.01")
    assert cot_usd.fuente == "simulado"
    assert cot_usd.fecha == date(2026, 11, 1)

    op_usd = Operacion(
        id="conv-usd-cop-1",
        tipo="conversion",
        desde="USD",
        hacia="COP",
        monto=Decimal("100.00"),
        categoria="arriendo",
        fecha_programada=date(2026, 11, 1),
    )
    res_usd = banco.ejecutar(op_usd)
    assert res_usd.ok is True

    esperado_cop_1 = (Decimal("100.00") * Decimal("4100.00") * (Decimal("1") - Decimal("0.01"))).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    assert esperado_cop_1 == Decimal("405900.00")
    assert _saldos_por_moneda(banco)["USD"] == Decimal("400.00")
    assert _saldos_por_moneda(banco)["COP"] == esperado_cop_1

    reloj.avanzar(4)  # 2026-11-05 -> TRM 4200.50
    op_usdt = Operacion(
        id="conv-usdt-cop-2",
        tipo="conversion",
        desde="USDT",
        hacia="COP",
        monto=Decimal("50.00"),
        categoria="internet",
        fecha_programada=date(2026, 11, 5),
    )
    res_usdt = banco.ejecutar(op_usdt)
    assert res_usdt.ok is True

    esperado_cop_2 = (Decimal("50.00") * Decimal("4200.50") * (Decimal("1") - Decimal("0.01"))).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    assert esperado_cop_2 == Decimal("207924.75")
    assert _saldos_por_moneda(banco)["USDT"] == Decimal("150.00")
    assert _saldos_por_moneda(banco)["COP"] == esperado_cop_1 + esperado_cop_2


def test_conversion_usd_a_usdt_uno_a_uno() -> None:
    reloj = RelojSimulado(date(2026, 11, 1))
    banco = BancoSimulado(reloj=reloj, mercado=_MercadoStub(_cotizaciones_prueba()))

    cot = banco.cotizacion("USD", "USDT")
    assert cot.tasa == Decimal("1")
    assert cot.spread == Decimal("0")
    assert cot.fuente == "simulado"

    cot_inv = banco.cotizacion("USDT", "USD")
    assert cot_inv.tasa == Decimal("1")
    assert cot_inv.spread == Decimal("0")

    op = Operacion(
        id="conv-usd-usdt-1",
        tipo="conversion",
        desde="USD",
        hacia="USDT",
        monto=Decimal("250.50"),
        categoria="ahorro",
        fecha_programada=date(2026, 11, 1),
    )
    res = banco.ejecutar(op)
    assert res.ok is True

    saldos = _saldos_por_moneda(banco)
    assert saldos["USD"] == Decimal("749.50")
    assert saldos["USDT"] == Decimal("250.50")
    assert len(banco.movimientos()) == 1
    assert banco.movimientos()[0].tipo == "conversion"


def test_pago_usd_cop_y_rechazo_por_saldo_insuficiente() -> None:
    reloj = RelojSimulado(date(2026, 11, 1))
    registro = Registro(":memory:")
    banco = BancoSimulado(
        reloj=reloj,
        mercado=_MercadoStub(_cotizaciones_prueba()),
        registro=registro,
        saldos_iniciales={
            "USD": Decimal("100.00"),
            "COP": Decimal("500000.00"),
            "USDT": Decimal("0.00"),
        },
    )

    pago_cop = Operacion(
        id="pago-cop-1",
        tipo="pago",
        desde="COP",
        monto=Decimal("200000.00"),
        categoria="arriendo",
        fecha_programada=date(2026, 11, 1),
    )
    assert banco.ejecutar(pago_cop).ok is True

    pago_usd = Operacion(
        id="pago-usd-1",
        tipo="pago",
        desde="USD",
        monto=Decimal("40.00"),
        categoria="suscripcion",
        fecha_programada=date(2026, 11, 1),
    )
    assert banco.ejecutar(pago_usd).ok is True

    saldos_antes = _saldos_por_moneda(banco)
    movs_antes = len(banco.movimientos())

    pago_sin_fondos = Operacion(
        id="pago-sin-fondos",
        tipo="pago",
        desde="USD",
        monto=Decimal("60.01"),
        categoria="arriendo",
        fecha_programada=date(2026, 11, 1),
    )
    res_fallo = banco.ejecutar(pago_sin_fondos)

    assert res_fallo.ok is False
    assert "Saldo insuficiente" in res_fallo.mensaje
    assert _saldos_por_moneda(banco) == saldos_antes
    assert len(banco.movimientos()) == movs_antes
    assert registro.ya_ejecutada("pago-sin-fondos") is False


def test_reintento_mismo_id_tras_fallo_registra_el_exito() -> None:
    reloj = RelojSimulado(date(2026, 11, 1))
    registro = Registro(":memory:")
    banco = BancoSimulado(
        reloj=reloj,
        mercado=_MercadoStub(_cotizaciones_prueba()),
        registro=registro,
        saldos_iniciales={"USD": Decimal("0"), "COP": Decimal("0"), "USDT": Decimal("0")},
    )
    op = Operacion(
        id="reintento-fondos",
        tipo="conversion",
        desde="USD",
        hacia="USDT",
        monto=Decimal("50"),
        categoria="ahorro",
        fecha_programada=date(2026, 11, 1),
    )

    assert banco.ejecutar(op).ok is False
    banco.recibir_pago(Decimal("50"))
    assert banco.ejecutar(op).ok is True
    assert banco.ejecutar(op).ok is False
    assert registro.ya_ejecutada(op.id) is True
    assert _saldos_por_moneda(banco)["USDT"] == Decimal("50")
    registro.cerrar()


def test_ejecuciones_concurrentes_no_sobregiran_saldo() -> None:
    banco = BancoSimulado(
        reloj=RelojSimulado(date(2026, 11, 1)),
        mercado=_MercadoStub(_cotizaciones_prueba()),
        saldos_iniciales={"USD": Decimal("1000"), "COP": Decimal("0"), "USDT": Decimal("0")},
    )
    operaciones = [
        Operacion(
            id=f"pago-race-{i}",
            tipo="pago",
            desde="USD",
            monto=Decimal("700"),
            categoria="prueba",
            fecha_programada=date(2026, 11, 1),
        )
        for i in range(2)
    ]

    with ThreadPoolExecutor(max_workers=2) as pool:
        resultados = list(pool.map(banco.ejecutar, operaciones))

    assert sum(resultado.ok for resultado in resultados) == 1
    assert _saldos_por_moneda(banco)["USD"] == Decimal("300")
    assert len(banco.movimientos()) == 1


def test_recibir_pago_y_rendimiento_diario() -> None:
    reloj = RelojSimulado(date(2026, 11, 1))
    banco = BancoSimulado(
        reloj=reloj,
        mercado=_MercadoStub(_cotizaciones_prueba()),
        saldos_iniciales={"USD": Decimal("0.00"), "COP": Decimal("0.00"), "USDT": Decimal("0.00")},
    )

    assert banco.aplicar_rendimiento_diario() is None

    ingreso = banco.recibir_pago(Decimal("200.00"), "Pago cliente ACME")
    assert ingreso.tipo == "ingreso"
    assert ingreso.moneda == "USD"
    assert ingreso.monto == Decimal("200.00")
    assert _saldos_por_moneda(banco)["USD"] == Decimal("200.00")

    res_conv = banco.ejecutar(
        Operacion(
            id="conv-ahorro",
            tipo="conversion",
            desde="USD",
            hacia="USDT",
            monto=Decimal("170.00"),
            categoria="ahorro",
            fecha_programada=date(2026, 11, 1),
        )
    )
    assert res_conv.ok is True

    rend_usdt = banco.rendimiento("USDT")
    assert rend_usdt.tasa_anual == Decimal("0.10")
    assert rend_usdt.fuente == "simulado"
    assert banco.rendimiento("USD").tasa_anual == Decimal("0")

    mov_rend = banco.aplicar_rendimiento_diario()
    assert mov_rend is not None
    assert mov_rend.tipo == "rendimiento"
    assert mov_rend.moneda == "USDT"
    assert mov_rend.monto > Decimal("0")
    assert mov_rend.monto == Decimal("0.0466")
    assert _saldos_por_moneda(banco)["USDT"] == Decimal("170.0466")


def test_idempotencia_persistente_entre_instancias_sqlite(tmp_path: Path) -> None:
    ruta_db = tmp_path / "banco_registro.sqlite"
    reloj = RelojSimulado(date(2026, 11, 1))
    mercado = _MercadoStub(_cotizaciones_prueba())
    op = Operacion(
        id="op-persistente-1",
        tipo="conversion",
        desde="USD",
        hacia="USDT",
        monto=Decimal("120.00"),
        categoria="ahorro",
        fecha_programada=date(2026, 11, 1),
    )

    reg1 = Registro(ruta_db)
    banco1 = BancoSimulado(reloj=reloj, mercado=mercado, registro=reg1)
    res1 = banco1.ejecutar(op)
    assert res1.ok is True
    assert _saldos_por_moneda(banco1)["USD"] == Decimal("880.00")
    reg1.cerrar()

    reg2 = Registro(ruta_db)
    banco2 = BancoSimulado(reloj=reloj, mercado=mercado, registro=reg2)
    saldos_antes = banco2.saldos()
    res2 = banco2.ejecutar(op)

    assert res2.ok is False
    assert res2.operacion_id == op.id
    assert banco2.saldos() == saldos_antes
    assert banco2.movimientos() == []
    reg2.cerrar()


def test_fabrica_modo_simulado_y_modos_pendientes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruta_db = tmp_path / "fabrica.sqlite"
    monkeypatch.setenv("BANCO_MODO", "simulado")
    monkeypatch.setenv("BANCO_SQLITE_PATH", str(ruta_db))

    assert fabrica.modo_actual() == "simulado"
    reloj = fabrica.obtener_reloj()
    assert isinstance(reloj, RelojSimulado)
    assert reloj.hoy() == date(2026, 11, 1)

    mercado = fabrica.obtener_mercado()
    assert isinstance(mercado, MercadoSocrata)

    banco = fabrica.obtener_banco(reloj)
    assert isinstance(banco, BancoSimulado)
    assert isinstance(banco, BancoPort)
    assert banco.reloj is reloj
    assert ruta_db.exists()
    banco.registro.cerrar()

    monkeypatch.delenv("BELO_API_URL", raising=False)
    monkeypatch.delenv("BELO_API_KEY", raising=False)
    monkeypatch.setenv("BANCO_MODO", "api")
    with pytest.raises(NotImplementedError, match="BANCO_MODO=api"):
        fabrica.obtener_banco()

    monkeypatch.delenv("BELO_MCP_URL", raising=False)
    monkeypatch.setenv("BANCO_MODO", "mcp")
    with pytest.raises(NotImplementedError, match="BANCO_MODO=mcp"):
        fabrica.obtener_banco()


# --------------------------------------------------------------------------- Mandatos AP2


def _op_conversion(op_id: str = "op-mandato-1") -> Operacion:
    """Operación de conversión determinista para las pruebas de mandatos."""
    return Operacion(
        id=op_id,
        tipo="conversion",
        desde="USD",
        hacia="USDT",
        monto=Decimal("50.00"),
        categoria="ahorro",
        fecha_programada=date(2026, 11, 27),
    )


def _banco_con_firmador(
    firmador: object,
    exigir_mandato: bool = False,
) -> BancoSimulado:
    reloj = RelojSimulado(date(2026, 11, 27))
    return BancoSimulado(
        reloj=reloj,
        mercado=_MercadoStub(_cotizaciones_prueba()),
        firmador=firmador,  # type: ignore[arg-type]
        exigir_mandato=exigir_mandato,
        saldos_iniciales={
            "USD": Decimal("200.00"),
            "COP": Decimal("0.00"),
            "USDT": Decimal("0.00"),
        },
    )


def test_mandato_valido_resultado_verificado() -> None:
    """Un mandato AP2 válido produce `mandato_verificado=True` en el Resultado."""
    secreto = b"clave-test-ap2-segura"
    firmador = FirmadorMandatosAP2(secret_key=secreto)
    banco = _banco_con_firmador(firmador)

    op = _op_conversion()
    mandato = firmador.emitir(op, "hash-intent-prueba", ttl_segundos=600)

    res = banco.ejecutar(op, mandato=mandato)

    assert res.ok is True
    assert res.mandato_verificado is True
    assert res.mandato_id == mandato.id
    # El saldo debe haber cambiado
    saldos = {s.moneda: s.monto for s in banco.saldos()}
    assert saldos["USD"] == Decimal("150.00")
    assert saldos["USDT"] == Decimal("50.00")


def test_mandato_expirado_rechaza_sin_mover_saldos() -> None:
    """Un mandato AP2 expirado produce `ok=False, mandato_verificado=False` y no mueve saldos."""
    from datetime import datetime, timedelta, timezone

    secreto = b"clave-test-ap2-segura"
    firmador = FirmadorMandatosAP2(secret_key=secreto)
    banco = _banco_con_firmador(firmador)

    op = _op_conversion("op-expirado-1")

    # El reloj simulado marca 2026-11-27 12:00 UTC.
    # Emitimos el mandato con expiry 1 hora antes del ahora simulado → ya expiró.
    ahora_simulado = banco.reloj.ahora()
    emitido = ahora_simulado - timedelta(hours=2)
    expira = ahora_simulado - timedelta(hours=1)  # antes del "ahora" del banco

    # Firmamos manualmente para controlar los timestamps
    mandato_sin_firmar = PaymentMandate(
        operacion_id=op.id,
        intent_hash="hash-intent-prueba",
        monto=op.monto,
        moneda=op.desde,
        aprobacion="auto_politica",
        emitido_en=emitido,
        expira=expira,
        firma="",
    )
    import hmac as _hmac
    import hashlib as _hashlib
    from banco.mandatos import _json_canonico

    payload = _json_canonico(mandato_sin_firmar, excluir={"firma"})
    firma = _hmac.new(secreto, payload, _hashlib.sha256).hexdigest()
    mandato_expirado = mandato_sin_firmar.model_copy(update={"firma": firma})

    saldos_antes = {s.moneda: s.monto for s in banco.saldos()}
    res = banco.ejecutar(op, mandato=mandato_expirado)

    assert res.ok is False
    assert res.mandato_verificado is False
    assert "inválido o expirado" in res.mensaje
    assert {s.moneda: s.monto for s in banco.saldos()} == saldos_antes
    assert banco.movimientos() == []


def test_mandato_manipulado_rechaza_sin_mover_saldos() -> None:
    """Un mandato con firma manipulada produce `ok=False, mandato_verificado=False`."""
    secreto = b"clave-test-ap2-segura"
    firmador = FirmadorMandatosAP2(secret_key=secreto)
    banco = _banco_con_firmador(firmador)

    op = _op_conversion("op-manipulado-1")
    mandato_original = firmador.emitir(op, "hash-intent-prueba", ttl_segundos=600)

    # Manipular la firma para simular tampering
    mandato_manipulado = mandato_original.model_copy(update={"firma": "firma-falsa-aaaaaa"})

    saldos_antes = {s.moneda: s.monto for s in banco.saldos()}
    res = banco.ejecutar(op, mandato=mandato_manipulado)

    assert res.ok is False
    assert res.mandato_verificado is False
    assert {s.moneda: s.monto for s in banco.saldos()} == saldos_antes


def test_exigir_mandato_sin_mandato_rechaza() -> None:
    """Con `exigir_mandato=True` y sin pasar mandato, la operación se rechaza."""
    secreto = b"clave-test-ap2-segura"
    firmador = FirmadorMandatosAP2(secret_key=secreto)
    banco = _banco_con_firmador(firmador, exigir_mandato=True)

    op = _op_conversion("op-sin-mandato-1")

    saldos_antes = {s.moneda: s.monto for s in banco.saldos()}
    res = banco.ejecutar(op)  # sin mandato

    assert res.ok is False
    assert res.mandato_verificado is False
    assert "requerido" in res.mensaje
    assert {s.moneda: s.monto for s in banco.saldos()} == saldos_antes


def test_sin_exigir_mandato_sin_mandato_ejecuta_normal() -> None:
    """Sin `exigir_mandato` y sin pasar mandato, la operación se ejecuta normalmente."""
    secreto = b"clave-test-ap2-segura"
    firmador = FirmadorMandatosAP2(secret_key=secreto)
    banco = _banco_con_firmador(firmador, exigir_mandato=False)

    op = _op_conversion("op-libre-1")
    res = banco.ejecutar(op)

    assert res.ok is True
    assert res.mandato_verificado is None
    assert res.mandato_id is None
