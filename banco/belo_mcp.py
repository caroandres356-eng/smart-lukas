"""Adaptador del servidor MCP de Belo (vacío hasta tener acceso).

Usa BELO_MCP_URL del .env. Cada método llama a una herramienta del MCP y traduce
la respuesta a los modelos de core.modelos (fuente="belo", dinero en Decimal).
Los nombres exactos de las herramientas se confirman cuando llegue el acceso.
Cuando se llene: BANCO_MODO=mcp y correr tests/test_contrato_banco.py (quitar el skip).
"""

from __future__ import annotations

from core.modelos import Cotizacion, Moneda, Movimiento, Operacion, Rendimiento, Resultado, Saldo

PENDIENTE = "pendiente credenciales de Belo"


class BeloMcpBanco:
    def __init__(self, url: str | None = None) -> None:
        self.url = url

    def saldos(self) -> list[Saldo]:
        # Herramienta MCP: consulta de saldos.
        raise NotImplementedError(PENDIENTE)

    def cotizacion(self, desde: Moneda, hacia: Moneda) -> Cotizacion:
        # Herramienta MCP: cambio de divisas (cotizar, sin ejecutar).
        raise NotImplementedError(PENDIENTE)

    def rendimiento(self, moneda: Moneda) -> Rendimiento:
        # Herramienta MCP: rendimientos.
        raise NotImplementedError(PENDIENTE)

    def ejecutar(self, op: Operacion) -> Resultado:
        # Herramientas MCP: aprobación / ejecución de transacciones (cambio de divisas o pago).
        # Nuestra bandeja decide CUÁNDO pedir permiso; Belo ejecuta. Pasar op.id para idempotencia.
        raise NotImplementedError(PENDIENTE)

    def movimientos(self) -> list[Movimiento]:
        # Herramienta MCP: historial de movimientos/transacciones.
        raise NotImplementedError(PENDIENTE)
