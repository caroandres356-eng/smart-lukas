"""Adaptador de la API REST de Belo (vacío hasta tener credenciales).

Usa BELO_API_URL y BELO_API_KEY del .env, cliente httpx.
Cuando se llene: BANCO_MODO=api y correr tests/test_contrato_banco.py (quitar el skip).
Todo lo que devuelva lleva fuente="belo". El dinero se convierte a Decimal desde str, nunca float.
"""

from __future__ import annotations

from core.modelos import Cotizacion, Moneda, Movimiento, Operacion, Rendimiento, Resultado, Saldo

PENDIENTE = "pendiente credenciales de Belo"


class BeloApiBanco:
    def __init__(self, url: str | None = None, api_key: str | None = None) -> None:
        self.url = url
        self.api_key = api_key

    def saldos(self) -> list[Saldo]:
        # Traduce: endpoint de saldos/balances de la cuenta (ej. GET /balances).
        raise NotImplementedError(PENDIENTE)

    def cotizacion(self, desde: Moneda, hacia: Moneda) -> Cotizacion:
        # Traduce: endpoint de cotización / cambio de divisas (ej. GET /quotes?from=USD&to=COP).
        # Separar la tasa de mercado del spread que cobra Belo.
        raise NotImplementedError(PENDIENTE)

    def rendimiento(self, moneda: Moneda) -> Rendimiento:
        # Traduce: endpoint de rendimientos (ej. GET /yields) -> tasa anual como fracción.
        raise NotImplementedError(PENDIENTE)

    def ejecutar(self, op: Operacion) -> Resultado:
        # Traduce: endpoint de crear/ejecutar transacción (ej. POST /transactions o /swaps).
        # Enviar op.id como idempotency key. Si Belo tiene su propia aprobación, usarla aquí.
        raise NotImplementedError(PENDIENTE)

    def movimientos(self) -> list[Movimiento]:
        # Traduce: endpoint de historial de transacciones (ej. GET /transactions).
        raise NotImplementedError(PENDIENTE)
