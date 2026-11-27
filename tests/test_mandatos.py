"""Tests de contrato y seguridad fail-closed para `banco/mandatos.py` (AP2)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from banco.mandatos import (
    FirmadorMandatosAP2,
    IntentMandate,
    MandatoPort,
    PaymentMandate,
    QuoteMandate,
    emitir_payment_mandate,
    hash_canonico,
    verificar_mandato,
)
from core.modelos import Operacion


def _ahora() -> datetime:
    return datetime(2026, 11, 27, 15, 0, 0, tzinfo=timezone.utc)


def _operacion(**cambios) -> Operacion:
    datos = dict(
        tipo="conversion",
        desde="USD",
        hacia="COP",
        monto=Decimal("250.00"),
        categoria="arriendo",
        fecha_programada=date(2026, 11, 27),
    )
    datos.update(cambios)
    return Operacion(**datos)


def _intent(ahora: datetime | None = None) -> IntentMandate:
    base = ahora or _ahora()
    return IntentMandate(
        politica_hash="abc123politica",
        max_usd_operacion=Decimal("300.00"),
        max_usd_dia=Decimal("500.00"),
        categorias_bloqueadas=["apuestas"],
        creado=base,
        expira=base + timedelta(hours=24),
    )


def _quote(ahora: datetime | None = None) -> QuoteMandate:
    base = ahora or _ahora()
    return QuoteMandate(
        desde="USD",
        hacia="COP",
        tasa=Decimal("4100.50"),
        spread=Decimal("0.01"),
        cotizado_en=base,
        expira=base + timedelta(minutes=5),
    )


def test_modelos_ap2_extra_forbid_y_fechas_utc():
    naive = datetime(2026, 11, 27, 15, 0, 0)
    intent = IntentMandate(
        politica_hash="h1",
        max_usd_operacion=Decimal("300"),
        max_usd_dia=Decimal("500"),
        creado=naive,
        expira=naive + timedelta(hours=1),
    )
    assert intent.creado.tzinfo == timezone.utc
    assert intent.expira.tzinfo == timezone.utc

    quote = QuoteMandate(
        desde="USD",
        hacia="COP",
        tasa=Decimal("4000"),
        spread=Decimal("0.01"),
        cotizado_en=naive,
        expira=naive + timedelta(minutes=5),
    )
    assert quote.cotizado_en.tzinfo == timezone.utc
    assert quote.expira.tzinfo == timezone.utc

    with pytest.raises(ValidationError):
        IntentMandate(
            politica_hash="h1",
            max_usd_operacion=Decimal("300"),
            max_usd_dia=Decimal("500"),
            creado=naive,
            expira=naive,
            campo_extra="no_permitido",
        )

    with pytest.raises(ValidationError):
        QuoteMandate(
            desde="USD",
            hacia="COP",
            tasa=Decimal("0"),
            spread=Decimal("0.01"),
            cotizado_en=naive,
            expira=naive,
        )

    with pytest.raises(ValidationError):
        PaymentMandate(
            operacion_id="op1",
            intent_hash="ih1",
            monto=Decimal("10"),
            moneda="USD",
            aprobacion="auto_politica",
            emitido_en=naive,
            expira=naive,
            extra="prohibido",
        )


def test_firmador_cumple_mandato_port():
    firmador = FirmadorMandatosAP2(secret_key="secreto-de-prueba")
    assert isinstance(firmador, MandatoPort)


def test_hash_canonico_es_determinista():
    ahora = _ahora()
    a = _intent(ahora)
    b = a.model_copy()
    assert hash_canonico(a) == hash_canonico(b)

    c = a.model_copy(update={"max_usd_operacion": Decimal("350.00")})
    assert hash_canonico(a) != hash_canonico(c)


def test_emitir_y_verificar_mandato_valido(monkeypatch):
    monkeypatch.setenv("MANDATO_SECRET_KEY", "llave-super-secreta")
    ahora = _ahora()
    op = _operacion()
    intent = _intent(ahora)
    quote = _quote(ahora)

    mandato = emitir_payment_mandate(
        op,
        intent,
        quote=quote,
        aprobacion="humana_solo_esta_vez",
        solicitud_id="sol-001",
        emitido_en=ahora,
        ttl_segundos=120,
    )

    assert mandato.firma != ""
    assert mandato.operacion_id == op.id
    assert mandato.intent_hash == hash_canonico(intent)
    assert mandato.quote_hash == hash_canonico(quote)
    assert mandato.monto == op.monto
    assert mandato.moneda == op.desde
    assert mandato.solicitud_id == "sol-001"
    assert verificar_mandato(mandato, ahora + timedelta(seconds=119), op) is True


def test_verificar_falla_si_manipulan_monto():
    ahora = _ahora()
    firmador = FirmadorMandatosAP2(secret_key="llave-prueba")
    op = _operacion(monto=Decimal("100.00"))
    mandato = firmador.emitir(op, _intent(ahora), emitido_en=ahora, ttl_segundos=300)

    op_alterada = op.model_copy(update={"monto": Decimal("100.01")})
    assert firmador.verificar(mandato, ahora + timedelta(seconds=10), op_alterada) is False

    mandato_alterado = mandato.model_copy(update={"monto": Decimal("100.01")})
    assert firmador.verificar(mandato_alterado, ahora + timedelta(seconds=10), op) is False
    assert firmador.verificar(mandato_alterado, ahora + timedelta(seconds=10), op_alterada) is False


def test_verificar_falla_si_expiro():
    ahora = _ahora()
    firmador = FirmadorMandatosAP2(secret_key="llave-prueba")
    op = _operacion()
    mandato = firmador.emitir(op, _intent(ahora), emitido_en=ahora, ttl_segundos=60)

    assert firmador.verificar(mandato, ahora + timedelta(seconds=60), op) is False
    assert firmador.verificar(mandato, ahora + timedelta(seconds=61), op) is False


def test_verificar_falla_con_firma_invalida_o_secreto_distinto():
    ahora = _ahora()
    firmador_a = FirmadorMandatosAP2(secret_key="secreto-a")
    firmador_b = FirmadorMandatosAP2(secret_key="secreto-b")
    op = _operacion()
    mandato = firmador_a.emitir(op, _intent(ahora), emitido_en=ahora, ttl_segundos=300)

    assert firmador_b.verificar(mandato, ahora + timedelta(seconds=10), op) is False

    firma_corrupta = ("0" if mandato.firma[0] != "0" else "1") + mandato.firma[1:]
    assert (
        firmador_a.verificar(
            mandato.model_copy(update={"firma": firma_corrupta}),
            ahora + timedelta(seconds=10),
            op,
        )
        is False
    )
    assert (
        firmador_a.verificar(
            mandato.model_copy(update={"firma": ""}),
            ahora + timedelta(seconds=10),
            op,
        )
        is False
    )


def test_verificar_falla_si_no_coincide_operacion_id_o_moneda():
    ahora = _ahora()
    firmador = FirmadorMandatosAP2(secret_key="llave-prueba")
    op = _operacion(desde="USD", monto=Decimal("50.00"))
    mandato = firmador.emitir(op, _intent(ahora), emitido_en=ahora, ttl_segundos=300)

    assert firmador.verificar(mandato, ahora + timedelta(seconds=5), op.model_copy(update={"id": "otro-id"})) is False
    assert firmador.verificar(mandato, ahora + timedelta(seconds=5), op.model_copy(update={"desde": "USDT"})) is False
    assert (
        firmador.verificar(
            mandato,
            ahora + timedelta(seconds=5),
            op.model_copy(update={"mandato_id": "otro-mandato"}),
        )
        is False
    )


def test_secreto_efimero_cuando_env_vacio(monkeypatch):
    monkeypatch.setenv("MANDATO_SECRET_KEY", "")
    ahora = _ahora()
    op = _operacion()
    mandato = emitir_payment_mandate(op, _intent(ahora), emitido_en=ahora, ttl_segundos=60)
    assert mandato.firma != ""
    assert verificar_mandato(mandato, ahora + timedelta(seconds=10), op) is True
