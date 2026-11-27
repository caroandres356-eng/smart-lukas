"""Adaptador del servidor MCP de Belo cumpliendo `BancoPort`.

Usa `BELO_MCP_URL` del `.env` (o parámetros explícitos). Puede operar de dos formas:
1. Mediante un `caller` inyectable (función `(nombre_tool, argumentos) -> Any`).
2. Mediante JSON-RPC 2.0 HTTP sobre `httpx` contra `BELO_MCP_URL`.

Todo lo que devuelve lleva `fuente="belo"`. El dinero se convierte a `Decimal`
sin pasar por `float` usando los mismos parsers que `belo_api.py`.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Callable

import httpx

from banco.belo_api import (
    PENDIENTE,
    _a_decimal,
    _decodificar_json,
    _limpiar,
    _parsear_cotizacion,
    _parsear_movimientos,
    _parsear_rendimiento,
    _parsear_resultado,
    _parsear_saldos,
    _serializar_operacion,
)
from core.modelos import Cotizacion, Moneda, Movimiento, Operacion, Rendimiento, Resultado, Saldo

# Mapeo predeterminado: método Python → nombre de herramienta MCP de Belo.
TOOLS_POR_DEFECTO: dict[str, str] = {
    "saldos": "get_balances",
    "cotizacion": "get_quote",
    "rendimiento": "get_yields",
    "ejecutar": "execute_transaction",
    "movimientos": "list_transactions",
}

_JSONRPC_ID = 1


def _extraer_resultado_jsonrpc(cuerpo: Any) -> Any:
    """Extrae el contenido útil de una respuesta JSON-RPC 2.0 de un servidor MCP."""
    if not isinstance(cuerpo, Mapping):
        return cuerpo

    # Formato JSON-RPC estándar: {"jsonrpc": "2.0", "id": ..., "result": {...}}
    if "result" in cuerpo:
        resultado = cuerpo["result"]
        # Soporte structuredContent (MCP extendido)
        if isinstance(resultado, Mapping) and "structuredContent" in resultado:
            return resultado["structuredContent"]
        # Soporte content[0].text con JSON incrustado
        if isinstance(resultado, Mapping) and "content" in resultado:
            contenido = resultado["content"]
            if isinstance(contenido, list) and contenido:
                primer = contenido[0]
                if isinstance(primer, Mapping) and "text" in primer:
                    try:
                        return _decodificar_json(primer["text"])
                    except Exception:
                        return primer["text"]
        return resultado

    # Si no hay "result", devolver tal cual (puede ser error o formato distinto)
    return cuerpo


class BeloMcpBanco:
    """Adaptador del servidor MCP de Belo cumpliendo `BancoPort`.

    Variables de entorno soportadas cuando no se pasan al constructor:
    - `BELO_MCP_URL`: URL del servidor MCP de Belo.

    Parámetros:
        url:        URL base del servidor MCP (JSON-RPC 2.0 vía HTTP/SSE).
        caller:     Función `(nombre_tool, argumentos) -> Any` inyectable para tests y
                    entornos con cliente MCP propio. Si se provee, tiene prioridad sobre `url`.
        transport:  Transport `httpx` inyectable (para tests con `MockTransport`).
        timeout:    Segundos de espera por llamada HTTP (por defecto 10 s).
    """

    def __init__(
        self,
        url: str | None = None,
        *,
        caller: Callable[[str, dict], Any] | None = None,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.url: str | None = _limpiar(os.getenv("BELO_MCP_URL") if url is None else url, quitar_barra=True)
        self._caller = caller
        self._transport = transport
        self.timeout = timeout

    def esta_configurado(self) -> bool:
        """Retorna `True` si hay URL del MCP o caller inyectado."""
        return bool(self.url or self._caller is not None)

    # ---------------------------------------------------------------------- interno

    def _llamar_tool(self, nombre_tool: str, argumentos: dict) -> Any:
        """Invoca una herramienta MCP y devuelve el resultado parseado.

        - Sin configuración: lanza `NotImplementedError`.
        - Con `caller`: delega directamente.
        - Con `url`: envía JSON-RPC 2.0 y extrae `result`.
        """
        if not self.esta_configurado():
            raise NotImplementedError(PENDIENTE)

        if self._caller is not None:
            return self._caller(nombre_tool, argumentos)

        # Llamada HTTP JSON-RPC 2.0
        payload = {
            "jsonrpc": "2.0",
            "id": _JSONRPC_ID,
            "method": "tools/call",
            "params": {"name": nombre_tool, "arguments": argumentos},
        }
        with httpx.Client(
            timeout=self.timeout,
            transport=self._transport,
        ) as client:
            respuesta = client.post(
                self.url or "",
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            respuesta.raise_for_status()
            cuerpo = _decodificar_json(respuesta.text)

        return _extraer_resultado_jsonrpc(cuerpo)

    # ---------------------------------------------------------------------- BancoPort

    def saldos(self) -> list[Saldo]:
        """Consulta saldos actuales invocando `get_balances` en el MCP."""
        datos = self._llamar_tool(TOOLS_POR_DEFECTO["saldos"], {})
        return _parsear_saldos(datos)

    def cotizacion(self, desde: Moneda, hacia: Moneda) -> Cotizacion:
        """Cotiza cambio de divisas invocando `get_quote` en el MCP."""
        datos = self._llamar_tool(TOOLS_POR_DEFECTO["cotizacion"], {"from": desde, "to": hacia})
        return _parsear_cotizacion(datos, desde=desde, hacia=hacia)

    def rendimiento(self, moneda: Moneda) -> Rendimiento:
        """Consulta rendimiento anual invocando `get_yields` en el MCP."""
        datos = self._llamar_tool(TOOLS_POR_DEFECTO["rendimiento"], {"currency": moneda})
        return _parsear_rendimiento(datos, moneda=moneda)

    def ejecutar(self, op: Operacion) -> Resultado:
        """Ejecuta conversión o pago vía `execute_transaction` del MCP (idempotente por `op.id`)."""
        payload = _serializar_operacion(op)
        payload["idempotency_key"] = op.id
        datos = self._llamar_tool(TOOLS_POR_DEFECTO["ejecutar"], payload)
        return _parsear_resultado(datos, op.id)

    def movimientos(self) -> list[Movimiento]:
        """Lista movimientos históricos invocando `list_transactions` en el MCP."""
        datos = self._llamar_tool(TOOLS_POR_DEFECTO["movimientos"], {})
        return _parsear_movimientos(datos)
