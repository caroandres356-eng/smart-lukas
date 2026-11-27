"""Pruebas unitarias para RelojSimulado y Registro SQLite."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from banco.registro import Registro
from banco.reloj import RelojSimulado
from core.modelos import Operacion, Resultado
from core.puertos import Reloj


def _operacion_ejemplo(
    op_id: str = "op-001",
    *,
    mandato_id: str | None = None,
    mandato_firma: str | None = None,
) -> Operacion:
    return Operacion(
        id=op_id,
        tipo="conversion",
        desde="USD",
        hacia="COP",
        monto=Decimal("100.50"),
        categoria="ahorro",
        fecha_programada=date(2026, 11, 1),
        mandato_id=mandato_id,
        mandato_firma=mandato_firma,
    )


# --------------------------------------------------------------------------- RelojSimulado


def test_reloj_cumple_protocolo_y_inicio_con_date() -> None:
    inicio = date(2026, 11, 1)
    reloj = RelojSimulado(inicio)

    assert isinstance(reloj, Reloj)
    assert reloj.inicio == inicio
    assert reloj.hoy() == date(2026, 11, 1)
    ahora = reloj.ahora()
    assert ahora == datetime(2026, 11, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert ahora.tzinfo is timezone.utc


def test_reloj_inicio_con_datetime_naive_y_aware() -> None:
    reloj_naive = RelojSimulado(datetime(2026, 11, 1, 8, 30, 0))
    assert reloj_naive.ahora() == datetime(2026, 11, 1, 8, 30, 0, tzinfo=timezone.utc)
    assert reloj_naive.ahora().tzinfo is timezone.utc
    assert reloj_naive.hoy() == date(2026, 11, 1)

    tz_bogota = timezone(timedelta(hours=-5))
    reloj_aware = RelojSimulado(datetime(2026, 11, 1, 20, 0, 0, tzinfo=tz_bogota))
    assert reloj_aware.ahora() == datetime(2026, 11, 2, 1, 0, 0, tzinfo=timezone.utc)
    assert reloj_aware.ahora().tzinfo is timezone.utc
    assert reloj_aware.hoy() == date(2026, 11, 2)


def test_reloj_avanzar_dias_y_segundos() -> None:
    reloj = RelojSimulado(date(2026, 11, 1))

    reloj.avanzar(7)
    assert reloj.hoy() == date(2026, 11, 8)
    assert reloj.ahora() == datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)

    reloj.avanzar_segundos(43200.5)  # 12 horas y 0.5 segundos -> cambia al día 9
    assert reloj.hoy() == date(2026, 11, 9)
    assert reloj.ahora() == datetime(2026, 11, 9, 0, 0, 0, 500000, tzinfo=timezone.utc)
    assert reloj.ahora().tzinfo is timezone.utc


# --------------------------------------------------------------------------- Registro


def test_registro_en_memoria_guardar_obtener_listar_y_ya_ejecutada() -> None:
    reg = Registro(":memory:")
    try:
        assert reg.listar() == []
        assert reg.obtener("inexistente") is None
        assert reg.ya_ejecutada("inexistente") is False

        op_ok = _operacion_ejemplo("op-ok", mandato_id="mand-1", mandato_firma="firma-1")
        res_ok = Resultado(operacion_id="op-ok", ok=True, mensaje="Ejecutada")
        reg.guardar(op_ok, res_ok)

        op_fail = _operacion_ejemplo("op-fail")
        res_fail = Resultado(
            operacion_id="op-fail",
            ok=False,
            mensaje="Fondos insuficientes",
            mandato_id="mand-res",
        )
        reg.guardar(op_fail, res_fail)

        assert reg.ya_ejecutada("op-ok") is True
        assert reg.ya_ejecutada("op-fail") is False

        fila_ok = reg.obtener("op-ok")
        assert fila_ok is not None
        assert fila_ok["id"] == "op-ok"
        assert fila_ok["ok"] is True
        assert fila_ok["mensaje"] == "Ejecutada"
        assert fila_ok["mandato_id"] == "mand-1"
        assert fila_ok["mandato_firma"] == "firma-1"
        assert datetime.fromisoformat(fila_ok["creada"]).tzinfo is timezone.utc
        assert Operacion.model_validate_json(fila_ok["json"]) == op_ok

        fila_fail = reg.obtener("op-fail")
        assert fila_fail is not None
        assert fila_fail["ok"] is False
        assert fila_fail["mandato_id"] == "mand-res"

        lista = reg.listar()
        assert [item["id"] for item in lista] == ["op-ok", "op-fail"]
    finally:
        reg.cerrar()


def test_registro_persistencia_entre_instancias_e_idempotencia(tmp_path) -> None:
    ruta_db = tmp_path / "anidado" / "db.sqlite"

    reg1 = Registro(ruta_db)
    op = _operacion_ejemplo("op-persist")
    reg1.guardar(op, Resultado(operacion_id=op.id, ok=True, mensaje="Primera vez"))
    # Reintento con el mismo id no debe sobrescribir ni duplicar
    reg1.guardar(op, Resultado(operacion_id=op.id, ok=False, mensaje="Sobrescritura"))
    reg1.cerrar()

    assert ruta_db.exists()

    reg2 = Registro(ruta_db)
    try:
        assert reg2.ya_ejecutada("op-persist") is True
        filas = reg2.listar()
        assert len(filas) == 1
        assert filas[0]["ok"] is True
        assert filas[0]["mensaje"] == "Primera vez"
    finally:
        reg2.cerrar()


def test_registro_reintento_exitoso_actualiza_fallo_previo() -> None:
    reg = Registro(":memory:")
    op = _operacion_ejemplo("op-reintento")
    try:
        reg.guardar(op, Resultado(operacion_id=op.id, ok=False, mensaje="Fondos insuficientes"))
        assert reg.ya_ejecutada(op.id) is False

        reg.guardar(op, Resultado(operacion_id=op.id, ok=True, mensaje="Ejecutada"))

        assert reg.ya_ejecutada(op.id) is True
        registro = reg.obtener(op.id)
        assert registro is not None
        assert registro["ok"] is True
        assert registro["mensaje"] == "Ejecutada"
    finally:
        reg.cerrar()


def test_registro_concurrencia_mismo_id(tmp_path) -> None:
    ruta_db = tmp_path / "db.sqlite"
    reg = Registro(ruta_db)
    op = _operacion_ejemplo("op-concurrente")

    def _intentar(i: int) -> None:
        reg.guardar(
            op,
            Resultado(operacion_id=op.id, ok=True, mensaje=f"hilo-{i}"),
        )

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(_intentar, range(24)))

        assert reg.ya_ejecutada("op-concurrente") is True
        filas = reg.listar()
        assert len(filas) == 1
        assert filas[0]["id"] == "op-concurrente"
    finally:
        reg.cerrar()
