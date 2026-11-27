"""Selector de adaptadores según BANCO_MODO en el .env (Persona 1).

    BANCO_MODO=fakes      -> fakes (funciona hoy, por defecto)
    BANCO_MODO=simulado   -> banco.simulado + banco.mercado + banco.reloj (Persona 1)
    BANCO_MODO=api        -> banco.belo_api (cuando lleguen credenciales)
    BANCO_MODO=mcp        -> banco.belo_mcp (cuando lleguen credenciales)

El resto del código solo llama a estas tres funciones; nunca importa un adaptador directo.
"""

from __future__ import annotations

import os

from core.puertos import BancoPort, MercadoPort, Reloj

MODOS = ("fakes", "simulado", "api", "mcp")


def modo_actual() -> str:
    modo = os.getenv("BANCO_MODO", "fakes").strip().lower() or "fakes"
    if modo not in MODOS:
        raise ValueError(f"BANCO_MODO='{modo}' no es válido. Opciones: {', '.join(MODOS)}")
    return modo


def _pendiente(modo: str, que: str) -> NotImplementedError:
    quien = "Persona 1 (banco)" if modo == "simulado" else "Persona 1 (banco) - pendiente credenciales de Belo"
    return NotImplementedError(f"{quien}: {que} para BANCO_MODO={modo}")


def obtener_reloj() -> Reloj:
    modo = modo_actual()
    if modo == "fakes":
        from fakes.fakes import RelojFalso

        return RelojFalso()
    raise _pendiente(modo, "obtener_reloj")  # Persona 1: RelojSimulado(inicio=...) para los demás modos


def obtener_mercado() -> MercadoPort:
    modo = modo_actual()
    if modo == "fakes":
        from fakes.fakes import MercadoFalso

        return MercadoFalso()
    raise _pendiente(modo, "obtener_mercado")  # Persona 1: MercadoCSV("banco/datos/trm.csv")


def obtener_banco(reloj: Reloj | None = None) -> BancoPort:
    modo = modo_actual()
    if modo == "fakes":
        from fakes.fakes import BancoFalso

        return BancoFalso()
    raise _pendiente(modo, "obtener_banco")  # Persona 1: BancoSimulado / BeloApiBanco / BeloMcpBanco
