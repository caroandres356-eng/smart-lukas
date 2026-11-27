"""Tests de los adaptadores BeloApiBanco y BeloMcpBanco.

Cubre:
- Sin credenciales: esta_configurado() is False y NotImplementedError en los 5 métodos.
- BeloApiBanco con httpx.MockTransport: cabecera Authorization e Idempotency-Key,
  parsing correcto de Decimal, manejo de HTTP 409 idempotente, y los 5 métodos de BancoPort.
- BeloMcpBanco con caller mock y con httpx.MockTransport JSON-RPC para los 5 métodos.
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Any

import httpx
import pytest

from banco.belo_api import BeloApiBanco
from banco.belo_mcp import BeloMcpBanco, TOOLS_POR_DEFECTO
from core.modelos import Operacion, Saldo, Cotizacion, Rendimiento, Movimiento, Resultado


# ---------------------------------------------------------------------------
# Helpers / fixtures comunes
# ---------------------------------------------------------------------------

def _op(**kwargs) -> Operacion:
    """Crea una Operacion mínima válida."""
    datos: dict[str, Any] = {
        "tipo": "conversion",
        "desde": "USD",
        "hacia": "COP",
        "monto": Decimal("50.00"),
        "categoria": "prueba",
        "fecha_programada": date(2026, 11, 1),
    }
    datos.update(kwargs)
    return Operacion(**datos)


# Payloads JSON que simula Belo devuelve ---------------------------------

_RESP_SALDOS = json.dumps([
    {"currency": "USD", "amount": "1000.50"},
    {"currency": "COP", "amount": "4200000"},
    {"currency": "USDT", "amount": "500.75"},
])

_RESP_COTIZACION = json.dumps({
    "rate": "4200.123456",
    "spread": "0.01",
    "date": "2026-11-01",
})

_RESP_RENDIMIENTO = json.dumps({
    "currency": "USDT",
    "annual_rate": "0.085",
})

_RESP_TRANSACCION_OK = json.dumps({
    "ok": True,
    "mensaje": "Ejecutado correctamente",
})

_RESP_TRANSACCION_409 = json.dumps({
    "detail": "Operación duplicada",
})

_RESP_MOVIMIENTOS = json.dumps([
    {
        "id": "mov001",
        "date": "2026-10-01",
        "type": "deposit",
        "currency": "USD",
        "amount": "1000",
        "description": "Ingreso inicial",
    },
    {
        "id": "mov002",
        "date": "2026-11-01",
        "type": "payment",
        "currency": "COP",
        "amount": "500000",
        "description": "Pago arriendo",
    },
])


# ---------------------------------------------------------------------------
# ===========================================================================
# SECCIÓN 1: Sin credenciales
# ===========================================================================
# ---------------------------------------------------------------------------

class TestSinCredenciales:
    """Cuando no hay URL ni api_key, esta_configurado()=False y todos los métodos lanzan NotImplementedError."""

    def test_api_no_configurado(self, monkeypatch):
        monkeypatch.delenv("BELO_API_URL", raising=False)
        monkeypatch.delenv("BELO_API_KEY", raising=False)
        banco = BeloApiBanco()
        assert banco.esta_configurado() is False

    def test_mcp_no_configurado(self, monkeypatch):
        monkeypatch.delenv("BELO_MCP_URL", raising=False)
        banco = BeloMcpBanco()
        assert banco.esta_configurado() is False

    @pytest.mark.parametrize("metodo,args", [
        ("saldos", ()),
        ("cotizacion", ("USD", "COP")),
        ("rendimiento", ("USDT",)),
        ("ejecutar", (_op(),)),
        ("movimientos", ()),
    ])
    def test_api_lanza_not_implemented(self, monkeypatch, metodo, args):
        monkeypatch.delenv("BELO_API_URL", raising=False)
        monkeypatch.delenv("BELO_API_KEY", raising=False)
        banco = BeloApiBanco()
        with pytest.raises(NotImplementedError, match="pendiente credenciales de Belo"):
            getattr(banco, metodo)(*args)

    @pytest.mark.parametrize("metodo,args", [
        ("saldos", ()),
        ("cotizacion", ("USD", "COP")),
        ("rendimiento", ("USDT",)),
        ("ejecutar", (_op(),)),
        ("movimientos", ()),
    ])
    def test_mcp_lanza_not_implemented(self, monkeypatch, metodo, args):
        monkeypatch.delenv("BELO_MCP_URL", raising=False)
        banco = BeloMcpBanco()
        with pytest.raises(NotImplementedError, match="pendiente credenciales de Belo"):
            getattr(banco, metodo)(*args)


# ---------------------------------------------------------------------------
# ===========================================================================
# SECCIÓN 2: BeloApiBanco con MockTransport
# ===========================================================================
# ---------------------------------------------------------------------------

def _api_banco(handler) -> BeloApiBanco:
    """Crea un BeloApiBanco configurado con MockTransport."""
    return BeloApiBanco(
        url="https://api.belo.example",
        api_key="test-api-key-123",
        transport=httpx.MockTransport(handler),
    )


class TestBeloApiBancoCabeceras:
    """Verifica que las cabeceras Authorization e Idempotency-Key se envían correctamente."""

    def test_authorization_header_en_saldos(self):
        cabecera_recibida: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            cabecera_recibida.append(request.headers.get("authorization", ""))
            return httpx.Response(200, text=_RESP_SALDOS)

        banco = _api_banco(handler)
        banco.saldos()
        assert cabecera_recibida[0] == "Bearer test-api-key-123"

    def test_idempotency_key_en_ejecutar(self):
        idem_key_recibida: list[str] = []
        op = _op()

        def handler(request: httpx.Request) -> httpx.Response:
            idem_key_recibida.append(request.headers.get("idempotency-key", ""))
            return httpx.Response(200, text=_RESP_TRANSACCION_OK)

        banco = _api_banco(handler)
        banco.ejecutar(op)
        assert idem_key_recibida[0] == op.id

    def test_accept_json_header(self):
        accept_recibido: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            accept_recibido.append(request.headers.get("accept", ""))
            return httpx.Response(200, text=_RESP_SALDOS)

        banco = _api_banco(handler)
        banco.saldos()
        assert "application/json" in accept_recibido[0]


class TestBeloApiBancoSaldos:
    """Verifica parsing correcto de saldos."""

    def test_saldos_retorna_lista(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_SALDOS))
        saldos = banco.saldos()
        assert isinstance(saldos, list)
        assert len(saldos) == 3

    def test_saldos_monto_es_decimal(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_SALDOS))
        saldos = banco.saldos()
        for s in saldos:
            assert isinstance(s.monto, Decimal), f"monto debería ser Decimal, es {type(s.monto)}"

    def test_saldos_decimal_exacto(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_SALDOS))
        saldos = banco.saldos()
        usd = next(s for s in saldos if s.moneda == "USD")
        assert usd.monto == Decimal("1000.50")

    def test_saldos_fuente_belo(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_SALDOS))
        for s in banco.saldos():
            assert s.fuente == "belo"

    def test_saldos_acepta_wrapper_balances(self):
        resp = json.dumps({"balances": [{"currency": "USD", "amount": "999"}]})
        banco = _api_banco(lambda r: httpx.Response(200, text=resp))
        saldos = banco.saldos()
        assert len(saldos) == 1
        assert saldos[0].monto == Decimal("999")

    def test_saldos_llama_endpoint_correcto(self):
        path_recibido: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            path_recibido.append(request.url.path)
            return httpx.Response(200, text=_RESP_SALDOS)

        banco = _api_banco(handler)
        banco.saldos()
        assert path_recibido[0] == "/balances"


class TestBeloApiBancoCotizacion:
    """Verifica parsing de cotización."""

    def test_cotizacion_retorna_cotizacion(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_COTIZACION))
        c = banco.cotizacion("USD", "COP")
        assert isinstance(c, Cotizacion)

    def test_cotizacion_tasa_decimal(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_COTIZACION))
        c = banco.cotizacion("USD", "COP")
        assert isinstance(c.tasa, Decimal)
        assert c.tasa == Decimal("4200.123456")

    def test_cotizacion_spread_decimal(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_COTIZACION))
        c = banco.cotizacion("USD", "COP")
        assert isinstance(c.spread, Decimal)
        assert c.spread == Decimal("0.01")

    def test_cotizacion_fuente_belo(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_COTIZACION))
        c = banco.cotizacion("USD", "COP")
        assert c.fuente == "belo"

    def test_cotizacion_fecha_es_date(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_COTIZACION))
        c = banco.cotizacion("USD", "COP")
        assert isinstance(c.fecha, date)
        assert c.fecha == date(2026, 11, 1)

    def test_cotizacion_params_correctos(self):
        params_recibidos: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            params_recibidos.append(str(request.url.query))
            return httpx.Response(200, text=_RESP_COTIZACION)

        banco = _api_banco(handler)
        banco.cotizacion("USD", "COP")
        assert "from=USD" in params_recibidos[0]
        assert "to=COP" in params_recibidos[0]

    def test_cotizacion_sin_spread_default_cero(self):
        resp = json.dumps({"rate": "4100.00", "date": "2026-11-01"})
        banco = _api_banco(lambda r: httpx.Response(200, text=resp))
        c = banco.cotizacion("USD", "COP")
        assert c.spread == Decimal("0")

    def test_cotizacion_sin_fecha_default_hoy(self):
        resp = json.dumps({"rate": "4100.00"})
        banco = _api_banco(lambda r: httpx.Response(200, text=resp))
        c = banco.cotizacion("USD", "COP")
        from datetime import datetime, timezone
        assert c.fecha == datetime.now(timezone.utc).date()


class TestBeloApiBancoRendimiento:
    """Verifica parsing de rendimientos."""

    def test_rendimiento_retorna_rendimiento(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_RENDIMIENTO))
        r = banco.rendimiento("USDT")
        assert isinstance(r, Rendimiento)

    def test_rendimiento_tasa_decimal(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_RENDIMIENTO))
        r = banco.rendimiento("USDT")
        assert isinstance(r.tasa_anual, Decimal)
        assert r.tasa_anual == Decimal("0.085")

    def test_rendimiento_fuente_belo(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_RENDIMIENTO))
        r = banco.rendimiento("USDT")
        assert r.fuente == "belo"

    def test_rendimiento_moneda_correcta(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_RENDIMIENTO))
        r = banco.rendimiento("USDT")
        assert r.moneda == "USDT"

    def test_rendimiento_params_correctos(self):
        params_recibidos: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            params_recibidos.append(str(request.url.query))
            return httpx.Response(200, text=_RESP_RENDIMIENTO)

        banco = _api_banco(handler)
        banco.rendimiento("USDT")
        assert "currency=USDT" in params_recibidos[0]

    def test_rendimiento_lista_yields(self):
        resp = json.dumps({"yields": [
            {"currency": "USD", "annual_rate": "0.02"},
            {"currency": "USDT", "annual_rate": "0.085"},
        ]})
        banco = _api_banco(lambda r: httpx.Response(200, text=resp))
        r = banco.rendimiento("USDT")
        assert r.tasa_anual == Decimal("0.085")


class TestBeloApiBancoEjecutar:
    """Verifica ejecución de operaciones e idempotencia."""

    def test_ejecutar_ok(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_TRANSACCION_OK))
        res = banco.ejecutar(_op())
        assert isinstance(res, Resultado)
        assert res.ok is True

    def test_ejecutar_ok_operacion_id_correcto(self):
        op = _op()
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_TRANSACCION_OK))
        res = banco.ejecutar(op)
        assert res.operacion_id == op.id

    def test_ejecutar_409_es_ok_false(self):
        banco = _api_banco(lambda r: httpx.Response(409, text=_RESP_TRANSACCION_409))
        res = banco.ejecutar(_op())
        assert res.ok is False

    def test_ejecutar_409_mensaje_idempotencia(self):
        banco = _api_banco(lambda r: httpx.Response(409, text=_RESP_TRANSACCION_409))
        res = banco.ejecutar(_op())
        assert res.mensaje  # tiene mensaje descriptivo

    def test_ejecutar_envia_idempotency_key(self):
        recibidas: list[str] = []
        op = _op()

        def handler(request: httpx.Request) -> httpx.Response:
            recibidas.append(request.headers.get("idempotency-key", ""))
            return httpx.Response(200, text=_RESP_TRANSACCION_OK)

        banco = _api_banco(handler)
        banco.ejecutar(op)
        assert recibidas[0] == op.id

    def test_ejecutar_cuerpo_contiene_id_y_monto(self):
        body_recibido: list[bytes] = []
        op = _op()

        def handler(request: httpx.Request) -> httpx.Response:
            body_recibido.append(request.content)
            return httpx.Response(200, text=_RESP_TRANSACCION_OK)

        banco = _api_banco(handler)
        banco.ejecutar(op)
        payload = json.loads(body_recibido[0])
        assert payload["id"] == op.id
        assert payload["monto"] == str(op.monto)

    def test_ejecutar_monto_como_string_no_float(self):
        """El monto enviado en el body debe ser string, no float."""
        body_recibido: list[bytes] = []
        op = _op(monto=Decimal("123.456"))

        def handler(request: httpx.Request) -> httpx.Response:
            body_recibido.append(request.content)
            return httpx.Response(200, text=_RESP_TRANSACCION_OK)

        banco = _api_banco(handler)
        banco.ejecutar(op)
        # Verificar en el texto raw que no hay representación float con e-notation o imprecisión
        texto = body_recibido[0].decode()
        assert '"monto": "123.456"' in texto or '"monto":"123.456"' in texto

    def test_ejecutar_con_status_ok(self):
        resp = json.dumps({"status": "completed"})
        banco = _api_banco(lambda r: httpx.Response(200, text=resp))
        res = banco.ejecutar(_op())
        assert res.ok is True

    def test_ejecutar_con_ok_false(self):
        resp = json.dumps({"ok": False, "mensaje": "Fondos insuficientes"})
        banco = _api_banco(lambda r: httpx.Response(200, text=resp))
        res = banco.ejecutar(_op())
        assert res.ok is False
        assert "Fondos" in res.mensaje

    def test_ejecutar_con_mandato(self):
        recibido: list[dict] = []
        op = _op(mandato_id="mandato-abc", mandato_firma="firma-xyz")

        def handler(request: httpx.Request) -> httpx.Response:
            recibido.append(json.loads(request.content))
            return httpx.Response(200, text=_RESP_TRANSACCION_OK)

        banco = _api_banco(handler)
        banco.ejecutar(op)
        assert recibido[0].get("mandato_id") == "mandato-abc"
        assert recibido[0].get("mandato_firma") == "firma-xyz"


class TestBeloApiBancoMovimientos:
    """Verifica parsing del historial de movimientos."""

    def test_movimientos_retorna_lista(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_MOVIMIENTOS))
        movs = banco.movimientos()
        assert isinstance(movs, list)
        assert len(movs) == 2

    def test_movimientos_tipo_es_movimiento(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_MOVIMIENTOS))
        for m in banco.movimientos():
            assert isinstance(m, Movimiento)

    def test_movimientos_monto_decimal(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_MOVIMIENTOS))
        for m in banco.movimientos():
            assert isinstance(m.monto, Decimal)

    def test_movimientos_ordenados_cronologicamente(self):
        resp = json.dumps([
            {"id": "b", "date": "2026-11-01", "type": "payment", "currency": "COP", "amount": "100"},
            {"id": "a", "date": "2026-10-01", "type": "deposit", "currency": "USD", "amount": "50"},
        ])
        banco = _api_banco(lambda r: httpx.Response(200, text=resp))
        movs = banco.movimientos()
        assert movs[0].fecha <= movs[1].fecha

    def test_movimientos_tipo_mapeado(self):
        banco = _api_banco(lambda r: httpx.Response(200, text=_RESP_MOVIMIENTOS))
        movs = banco.movimientos()
        tipos = {m.tipo for m in movs}
        # "deposit" → "ingreso", "payment" → "pago"
        assert tipos == {"ingreso", "pago"}

    def test_movimientos_acepta_wrapper_transactions(self):
        resp = json.dumps({"transactions": [
            {"id": "x1", "date": "2026-11-15", "type": "ingreso", "currency": "USD", "amount": "200"},
        ]})
        banco = _api_banco(lambda r: httpx.Response(200, text=resp))
        movs = banco.movimientos()
        assert len(movs) == 1


class TestBeloApiBancoDecimalSinFloat:
    """Garantiza que nunca se pasa por float en las conversiones de Decimal."""

    def test_decimal_preciso_saldo(self):
        """Un valor con muchos decimales no debe perder precisión."""
        resp = json.dumps([{"currency": "USD", "amount": "1234567890.123456789"}])
        banco = _api_banco(lambda r: httpx.Response(200, text=resp))
        saldos = banco.saldos()
        assert saldos[0].monto == Decimal("1234567890.123456789")

    def test_decimal_preciso_cotizacion(self):
        resp = json.dumps({"rate": "4199.999999999", "spread": "0.0099999"})
        banco = _api_banco(lambda r: httpx.Response(200, text=resp))
        c = banco.cotizacion("USD", "COP")
        assert c.tasa == Decimal("4199.999999999")
        assert c.spread == Decimal("0.0099999")


# ---------------------------------------------------------------------------
# ===========================================================================
# SECCIÓN 3: BeloMcpBanco con caller mock
# ===========================================================================
# ---------------------------------------------------------------------------

class TestBeloMcpBancoConCaller:
    """Verifica comportamiento de BeloMcpBanco usando caller inyectado (mock)."""

    def _banco_con_caller(self, respuestas: dict[str, Any]) -> BeloMcpBanco:
        """Crea BeloMcpBanco con un caller que devuelve respuestas predefinidas."""
        def caller(nombre_tool: str, argumentos: dict) -> Any:
            if nombre_tool not in respuestas:
                raise ValueError(f"Tool inesperada: {nombre_tool}")
            return respuestas[nombre_tool]

        return BeloMcpBanco(caller=caller)

    def test_esta_configurado_con_caller(self):
        banco = BeloMcpBanco(caller=lambda n, a: None)
        assert banco.esta_configurado() is True

    def test_saldos_caller(self):
        datos = [
            {"currency": "USD", "amount": "1000"},
            {"currency": "COP", "amount": "4000000"},
            {"currency": "USDT", "amount": "200"},
        ]
        banco = self._banco_con_caller({TOOLS_POR_DEFECTO["saldos"]: datos})
        saldos = banco.saldos()
        assert len(saldos) == 3
        for s in saldos:
            assert isinstance(s.monto, Decimal)
            assert s.fuente == "belo"

    def test_cotizacion_caller(self):
        datos = {"rate": "4300.50", "spread": "0.015", "date": "2026-11-01"}
        banco = self._banco_con_caller({TOOLS_POR_DEFECTO["cotizacion"]: datos})
        c = banco.cotizacion("USD", "COP")
        assert isinstance(c, Cotizacion)
        assert c.tasa == Decimal("4300.50")
        assert c.fuente == "belo"

    def test_rendimiento_caller(self):
        datos = {"currency": "USDT", "annual_rate": "0.09"}
        banco = self._banco_con_caller({TOOLS_POR_DEFECTO["rendimiento"]: datos})
        r = banco.rendimiento("USDT")
        assert isinstance(r, Rendimiento)
        assert r.tasa_anual == Decimal("0.09")
        assert r.fuente == "belo"

    def test_ejecutar_caller_ok(self):
        datos = {"ok": True, "mensaje": "OK MCP"}
        banco = self._banco_con_caller({TOOLS_POR_DEFECTO["ejecutar"]: datos})
        res = banco.ejecutar(_op())
        assert isinstance(res, Resultado)
        assert res.ok is True

    def test_ejecutar_caller_fallo(self):
        datos = {"ok": False, "mensaje": "Error MCP"}
        banco = self._banco_con_caller({TOOLS_POR_DEFECTO["ejecutar"]: datos})
        res = banco.ejecutar(_op())
        assert res.ok is False
        assert "Error MCP" in res.mensaje

    def test_movimientos_caller(self):
        datos = [
            {"id": "m1", "date": "2026-10-15", "type": "ingreso", "currency": "USD", "amount": "300"},
            {"id": "m2", "date": "2026-11-01", "type": "pago", "currency": "COP", "amount": "150000"},
        ]
        banco = self._banco_con_caller({TOOLS_POR_DEFECTO["movimientos"]: datos})
        movs = banco.movimientos()
        assert len(movs) == 2
        for m in movs:
            assert isinstance(m, Movimiento)
            assert isinstance(m.monto, Decimal)

    def test_caller_recibe_nombre_tool_correcto(self):
        nombres_recibidos: list[str] = []

        def caller(nombre_tool: str, argumentos: dict) -> Any:
            nombres_recibidos.append(nombre_tool)
            return [{"currency": "USD", "amount": "1"}]

        banco = BeloMcpBanco(caller=caller)
        banco.saldos()
        assert nombres_recibidos[0] == TOOLS_POR_DEFECTO["saldos"]

    def test_caller_recibe_argumentos_cotizacion(self):
        args_recibidos: list[dict] = []

        def caller(nombre_tool: str, argumentos: dict) -> Any:
            args_recibidos.append(argumentos)
            return {"rate": "4200", "spread": "0.01"}

        banco = BeloMcpBanco(caller=caller)
        banco.cotizacion("USD", "COP")
        assert args_recibidos[0]["from"] == "USD"
        assert args_recibidos[0]["to"] == "COP"

    def test_caller_recibe_idempotency_key_en_ejecutar(self):
        args_recibidos: list[dict] = []
        op = _op()

        def caller(nombre_tool: str, argumentos: dict) -> Any:
            args_recibidos.append(argumentos)
            return {"ok": True}

        banco = BeloMcpBanco(caller=caller)
        banco.ejecutar(op)
        assert args_recibidos[0].get("idempotency_key") == op.id

    def test_decimal_sin_float_en_caller(self):
        datos = [{"currency": "USD", "amount": "9999999.123456789012345"}]
        banco = self._banco_con_caller({TOOLS_POR_DEFECTO["saldos"]: datos})
        saldos = banco.saldos()
        assert saldos[0].monto == Decimal("9999999.123456789012345")


# ---------------------------------------------------------------------------
# ===========================================================================
# SECCIÓN 4: BeloMcpBanco con MockTransport JSON-RPC
# ===========================================================================
# ---------------------------------------------------------------------------

def _jsonrpc_response(resultado: Any) -> str:
    """Genera respuesta JSON-RPC 2.0 estándar."""
    return json.dumps({"jsonrpc": "2.0", "id": 1, "result": resultado})


def _jsonrpc_response_structured(resultado: Any) -> str:
    """Genera respuesta JSON-RPC 2.0 con structuredContent."""
    return json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"structuredContent": resultado},
    })


def _jsonrpc_response_content_text(resultado: Any) -> str:
    """Genera respuesta JSON-RPC 2.0 con content[0].text."""
    return json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "result": {"content": [{"type": "text", "text": json.dumps(resultado)}]},
    })


def _mcp_banco(handler) -> BeloMcpBanco:
    """Crea un BeloMcpBanco configurado con MockTransport HTTP."""
    return BeloMcpBanco(
        url="https://mcp.belo.example",
        transport=httpx.MockTransport(handler),
    )


class TestBeloMcpBancoJsonRpc:
    """Verifica comportamiento de BeloMcpBanco con MockTransport JSON-RPC 2.0."""

    def test_esta_configurado_con_url(self):
        banco = BeloMcpBanco(url="https://mcp.belo.example")
        assert banco.esta_configurado() is True

    # --- Formato resultado directo ---

    def test_saldos_jsonrpc(self):
        datos = [
            {"currency": "USD", "amount": "800"},
            {"currency": "COP", "amount": "3200000"},
            {"currency": "USDT", "amount": "300"},
        ]
        banco = _mcp_banco(lambda r: httpx.Response(200, text=_jsonrpc_response(datos)))
        saldos = banco.saldos()
        assert len(saldos) == 3
        assert all(isinstance(s.monto, Decimal) for s in saldos)
        assert all(s.fuente == "belo" for s in saldos)

    def test_cotizacion_jsonrpc(self):
        datos = {"rate": "4350.00", "spread": "0.012", "date": "2026-11-15"}
        banco = _mcp_banco(lambda r: httpx.Response(200, text=_jsonrpc_response(datos)))
        c = banco.cotizacion("USD", "COP")
        assert c.tasa == Decimal("4350.00")
        assert c.fuente == "belo"

    def test_rendimiento_jsonrpc(self):
        datos = {"currency": "USDT", "annual_rate": "0.08"}
        banco = _mcp_banco(lambda r: httpx.Response(200, text=_jsonrpc_response(datos)))
        r = banco.rendimiento("USDT")
        assert r.tasa_anual == Decimal("0.08")
        assert r.fuente == "belo"

    def test_ejecutar_jsonrpc_ok(self):
        datos = {"ok": True, "mensaje": "Ejecutado"}
        banco = _mcp_banco(lambda r: httpx.Response(200, text=_jsonrpc_response(datos)))
        res = banco.ejecutar(_op())
        assert res.ok is True

    def test_movimientos_jsonrpc(self):
        datos = [
            {"id": "j1", "date": "2026-11-01", "type": "ingreso", "currency": "USD", "amount": "100"},
        ]
        banco = _mcp_banco(lambda r: httpx.Response(200, text=_jsonrpc_response(datos)))
        movs = banco.movimientos()
        assert len(movs) == 1
        assert isinstance(movs[0].monto, Decimal)

    # --- Formato structuredContent ---

    def test_saldos_structured_content(self):
        datos = [
            {"currency": "USD", "amount": "500"},
            {"currency": "COP", "amount": "2000000"},
            {"currency": "USDT", "amount": "150"},
        ]
        banco = _mcp_banco(lambda r: httpx.Response(200, text=_jsonrpc_response_structured(datos)))
        saldos = banco.saldos()
        assert len(saldos) == 3

    def test_cotizacion_structured_content(self):
        datos = {"rate": "4250", "spread": "0.005"}
        banco = _mcp_banco(lambda r: httpx.Response(200, text=_jsonrpc_response_structured(datos)))
        c = banco.cotizacion("USD", "COP")
        assert c.tasa == Decimal("4250")

    # --- Formato content[0].text ---

    def test_saldos_content_text(self):
        datos = [
            {"currency": "USD", "amount": "750"},
            {"currency": "COP", "amount": "2800000"},
            {"currency": "USDT", "amount": "400"},
        ]
        banco = _mcp_banco(lambda r: httpx.Response(200, text=_jsonrpc_response_content_text(datos)))
        saldos = banco.saldos()
        assert len(saldos) == 3
        usd = next(s for s in saldos if s.moneda == "USD")
        assert usd.monto == Decimal("750")

    def test_ejecutar_content_text(self):
        datos = {"ok": True, "mensaje": "OK via content text"}
        banco = _mcp_banco(lambda r: httpx.Response(200, text=_jsonrpc_response_content_text(datos)))
        res = banco.ejecutar(_op())
        assert res.ok is True

    # --- Verificación de la solicitud JSON-RPC enviada ---

    def test_jsonrpc_request_es_correcto(self):
        body_recibido: list[bytes] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body_recibido.append(request.content)
            return httpx.Response(200, text=_jsonrpc_response([]))

        banco = _mcp_banco(handler)
        banco.saldos()

        payload = json.loads(body_recibido[0])
        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "tools/call"
        assert payload["params"]["name"] == TOOLS_POR_DEFECTO["saldos"]

    def test_jsonrpc_cotizacion_argumentos(self):
        body_recibido: list[bytes] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body_recibido.append(request.content)
            return httpx.Response(200, text=_jsonrpc_response({"rate": "4200"}))

        banco = _mcp_banco(handler)
        banco.cotizacion("USD", "COP")

        payload = json.loads(body_recibido[0])
        args = payload["params"]["arguments"]
        assert args["from"] == "USD"
        assert args["to"] == "COP"

    def test_mcp_decimal_sin_float(self):
        datos = [{"currency": "USDT", "amount": "0.123456789012345678"}]
        banco = _mcp_banco(lambda r: httpx.Response(200, text=_jsonrpc_response(datos)))
        saldos = banco.saldos()
        assert saldos[0].monto == Decimal("0.123456789012345678")


# ---------------------------------------------------------------------------
# ===========================================================================
# SECCIÓN 5: Configuración normalización URL
# ===========================================================================
# ---------------------------------------------------------------------------

class TestNormalizacionUrl:
    """Verifica que las URLs se normalizan correctamente (trailing slash)."""

    def test_api_url_sin_barra_final(self, monkeypatch):
        monkeypatch.delenv("BELO_API_URL", raising=False)
        monkeypatch.delenv("BELO_API_KEY", raising=False)
        banco = BeloApiBanco(url="https://api.belo.example/", api_key="key")
        assert banco.url == "https://api.belo.example"

    def test_api_url_con_barra_multiple(self, monkeypatch):
        monkeypatch.delenv("BELO_API_URL", raising=False)
        monkeypatch.delenv("BELO_API_KEY", raising=False)
        banco = BeloApiBanco(url="https://api.belo.example///", api_key="key")
        assert banco.url is not None
        assert not banco.url.endswith("/")

    def test_mcp_url_normalizada(self, monkeypatch):
        monkeypatch.delenv("BELO_MCP_URL", raising=False)
        banco = BeloMcpBanco(url="https://mcp.belo.example/")
        assert banco.url is not None
        assert not banco.url.endswith("/")

    def test_api_lee_env_url(self, monkeypatch):
        monkeypatch.setenv("BELO_API_URL", "https://env.belo.example")
        monkeypatch.setenv("BELO_API_KEY", "env-key")
        banco = BeloApiBanco()
        assert banco.url == "https://env.belo.example"
        assert banco.api_key == "env-key"
        assert banco.esta_configurado() is True

    def test_mcp_lee_env_url(self, monkeypatch):
        monkeypatch.setenv("BELO_MCP_URL", "https://env-mcp.belo.example")
        banco = BeloMcpBanco()
        assert banco.url == "https://env-mcp.belo.example"
        assert banco.esta_configurado() is True
