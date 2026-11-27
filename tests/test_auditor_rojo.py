"""Tests de contrato y propiedades para El Auditor Rojo."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st
from pydantic import ValidationError

from auditor_rojo import (
    CATEGORIAS_ATAQUE,
    AgenteAuditablePort,
    CorredorAuditorRojo,
    EscenarioAdversario,
    ObjetivoContratoBase,
    ObjetivoSimuladoDefensivo,
    ReporteAuditoria,
    ResultadoEscenario,
    construir_reporte,
    generar_escenarios,
    renderizar_markdown,
)
from core.modelos import Operacion
from fakes.fakes import BancoFalso


class _ObjetivoMock:
    """Mock que cumple `AgenteAuditablePort` y bloquea todos los escenarios."""

    def __init__(self, fallar_ids: set[str] | None = None) -> None:
        self._fallar_ids = fallar_ids or set()
        self.llamadas: list[str] = []

    def ejecutar_escenario(self, escenario: EscenarioAdversario) -> ResultadoEscenario:
        self.llamadas.append(escenario.id)
        if escenario.id in self._fallar_ids:
            return ResultadoEscenario(
                escenario_id=escenario.id,
                categoria=escenario.categoria,
                bloqueado=False,
                motivo="Ataque no bloqueado en mock",
                paso=False,
            )
        return ResultadoEscenario(
            escenario_id=escenario.id,
            categoria=escenario.categoria,
            bloqueado=True,
            motivo="Bloqueado por guardia mock",
            paso=True,
        )


def _contiene_float(valor: Any) -> bool:
    if isinstance(valor, float):
        return True
    if isinstance(valor, dict):
        return any(_contiene_float(v) for v in valor.values())
    if isinstance(valor, list):
        return any(_contiene_float(v) for v in valor)
    return False


# --------------------------------------------------------------------------- modelos y generador


def test_modelos_prohiben_campos_extra() -> None:
    with pytest.raises(ValidationError):
        EscenarioAdversario(
            id="AR-1",
            categoria="prompt_injection",
            nombre="n",
            descripcion="d",
            extra_no_permitido=1,
        )
    with pytest.raises(ValidationError):
        ResultadoEscenario(
            escenario_id="AR-1",
            categoria="prompt_injection",
            bloqueado=True,
            motivo="ok",
            paso=True,
            extra_no_permitido=1,
        )
    with pytest.raises(ValidationError):
        ReporteAuditoria(
            total=0,
            pasados=0,
            fallados=0,
            tasa_exito=Decimal("0"),
            extra_no_permitido=1,
        )


def test_generar_escenarios_100_validos_unicos_y_deterministas() -> None:
    escenarios_a = generar_escenarios(100)
    escenarios_b = generar_escenarios(100)

    assert len(escenarios_a) == 100
    assert escenarios_a == escenarios_b
    assert all(isinstance(e, EscenarioAdversario) for e in escenarios_a)

    ids = {e.id for e in escenarios_a}
    assert len(ids) == 100

    categorias_presentes = {e.categoria for e in escenarios_a}
    assert categorias_presentes == set(CATEGORIAS_ATAQUE)

    for e in escenarios_a:
        assert not _contiene_float(e.payload), f"Payload con float en {e.id}"


def test_generar_escenarios_rechaza_cantidad_negativa() -> None:
    with pytest.raises(ValueError):
        generar_escenarios(-1)


# --------------------------------------------------------------------------- reporte


def test_construir_reporte_y_renderizar_markdown() -> None:
    resultados = [
        ResultadoEscenario(
            escenario_id="AR-001",
            categoria="prompt_injection",
            bloqueado=True,
            motivo="Bloqueado",
            paso=True,
        ),
        ResultadoEscenario(
            escenario_id="AR-002",
            categoria="cobro_duplicado",
            bloqueado=False,
            motivo="Permitió duplicado",
            paso=False,
        ),
        ResultadoEscenario(
            escenario_id="AR-003",
            categoria="cobro_duplicado",
            bloqueado=True,
            motivo="Idempotente",
            paso=True,
        ),
    ]

    reporte = construir_reporte(resultados)
    assert reporte.total == 3
    assert reporte.pasados == 2
    assert reporte.fallados == 1
    assert isinstance(reporte.tasa_exito, Decimal)
    assert reporte.tasa_exito == Decimal("0.6667")
    assert reporte.por_categoria["prompt_injection"] == {"total": 1, "pasados": 1, "fallados": 0}
    assert reporte.por_categoria["cobro_duplicado"] == {"total": 2, "pasados": 1, "fallados": 1}

    md = renderizar_markdown(reporte)
    assert "# Reporte de Auditoría — El Auditor Rojo" in md
    assert "66.67%" in md
    assert "`prompt_injection`" in md
    assert "`cobro_duplicado`" in md
    assert "AR-002" in md
    assert "Permitió duplicado" in md


def test_construir_reporte_vacio() -> None:
    reporte = construir_reporte([])
    assert reporte.total == 0
    assert reporte.tasa_exito == Decimal("0.0000")
    md = renderizar_markdown(reporte)
    assert "Todos los escenarios pasaron la auditoría." in md


# --------------------------------------------------------------------------- corredor y objetivo


def test_corredor_con_agente_mock() -> None:
    mock = _ObjetivoMock(fallar_ids={"AR-002"})
    assert isinstance(mock, AgenteAuditablePort)

    corredor = CorredorAuditorRojo(mock)
    reporte = corredor.correr(cantidad=12)

    assert len(mock.llamadas) == 12
    assert reporte.total == 12
    assert reporte.pasados == 11
    assert reporte.fallados == 1


def test_corredor_rechaza_objetivo_invalido() -> None:
    with pytest.raises(TypeError):
        CorredorAuditorRojo(object())  # type: ignore[arg-type]


def test_objetivo_contrato_base_verifica_idempotencia_y_modo_esqueleto() -> None:
    banco = BancoFalso()
    objetivo = ObjetivoContratoBase(banco=banco, modo_esqueleto=True)
    assert isinstance(objetivo, AgenteAuditablePort)

    escenarios = generar_escenarios(12)
    reporte = CorredorAuditorRojo(objetivo).correr(escenarios)

    duplicados = [r for r in reporte.resultados if r.categoria == "cobro_duplicado"]
    otros = [r for r in reporte.resultados if r.categoria != "cobro_duplicado"]

    assert len(duplicados) == 2
    assert all(r.bloqueado and r.paso for r in duplicados)
    assert all((not r.paso) and "[ESQUELETO]" in r.motivo for r in otros)


def test_objetivo_contrato_base_sin_modo_esqueleto_lanza_not_implemented() -> None:
    objetivo = ObjetivoContratoBase(banco=BancoFalso(), modo_esqueleto=False)
    escenario_llm = next(
        e for e in generar_escenarios(6) if e.categoria == "prompt_injection"
    )
    with pytest.raises(NotImplementedError):
        objetivo.ejecutar_escenario(escenario_llm)


def test_objetivo_contrato_base_rechaza_operacion_invalida() -> None:
    objetivo = ObjetivoContratoBase(banco=BancoFalso(), modo_esqueleto=False)
    escenario = EscenarioAdversario(
        id="AR-BAD-01",
        categoria="fuera_de_politica_persuasivo",
        nombre="Monto cero",
        descripcion="Intenta crear Operacion con monto 0",
        payload={
            "operacion": {
                "op_id": "bad-01",
                "tipo": "pago",
                "desde": "USD",
                "hacia": "COP",
                "monto": "0",
                "categoria": "arriendo",
                "fecha_programada": "2026-11-01",
            }
        },
    )
    res = objetivo.ejecutar_escenario(escenario)
    assert res.bloqueado is True
    assert res.paso is True


def test_objetivo_simulado_defensivo_pasa_bateria_completa_sin_red_ni_llm() -> None:
    reporte = CorredorAuditorRojo(ObjetivoSimuladoDefensivo()).correr(cantidad=100)

    assert reporte.total == 100
    assert reporte.pasados == 100
    assert reporte.fallados == 0


# --------------------------------------------------------------------------- hypothesis


@given(
    monto=st.decimals(
        max_value=Decimal("0"),
        allow_nan=False,
        allow_infinity=False,
    )
)
def test_propiedad_operacion_nunca_permite_montos_no_positivos(monto: Decimal) -> None:
    with pytest.raises(ValidationError):
        Operacion(
            tipo="conversion",
            desde="USD",
            hacia="COP",
            monto=monto,
            categoria="prueba",
            fecha_programada=date(2026, 11, 1),
        )


@given(
    op_id=st.text(min_size=1, max_size=24),
    monto=st.decimals(
        min_value=Decimal("0.01"),
        max_value=Decimal("100000.00"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    ),
    moneda=st.sampled_from(["USD", "COP", "USDT"]),
    categoria=st.text(min_size=1, max_size=20),
)
def test_propiedad_banco_falso_idempotencia_por_op_id(
    op_id: str,
    monto: Decimal,
    moneda: str,
    categoria: str,
) -> None:
    banco = BancoFalso()
    op = Operacion(
        id=op_id,
        tipo="pago",
        desde=moneda,  # type: ignore[arg-type]
        monto=monto,
        categoria=categoria,
        fecha_programada=date(2026, 11, 1),
    )

    primero = banco.ejecutar(op)
    movs_tras_primero = len(banco.movimientos())
    saldos_tras_primero = banco.saldos()

    segundo = banco.ejecutar(op)

    assert primero.ok is True
    assert segundo.ok is False
    assert segundo.operacion_id == op.id
    assert len(banco.movimientos()) == movs_tras_primero
    assert banco.saldos() == saldos_tras_primero


@given(
    total=st.integers(min_value=0, max_value=40),
    pasados=st.integers(min_value=0, max_value=40),
)
def test_propiedad_reporte_conserva_invariantes(total: int, pasados: int) -> None:
    assume(pasados <= total)
    resultados = [
        ResultadoEscenario(
            escenario_id=f"AR-{i:03d}",
            categoria=CATEGORIAS_ATAQUE[i % len(CATEGORIAS_ATAQUE)],
            bloqueado=i < pasados,
            motivo="m",
            paso=i < pasados,
        )
        for i in range(total)
    ]
    reporte = construir_reporte(resultados)
    assert reporte.total == total
    assert reporte.pasados == pasados
    assert reporte.fallados == total - pasados
    assert isinstance(reporte.tasa_exito, Decimal)
    assert Decimal("0") <= reporte.tasa_exito <= Decimal("1")
