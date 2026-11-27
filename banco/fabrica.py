"""Selector de adaptadores según BANCO_MODO en el .env (Persona 1).

    BANCO_MODO=fakes      -> fakes (funciona hoy, por defecto)
    BANCO_MODO=simulado   -> banco.simulado + banco.mercado + banco.reloj (Persona 1)
    BANCO_MODO=api        -> banco.belo_api (cuando lleguen credenciales)
    BANCO_MODO=mcp        -> banco.belo_mcp (cuando lleguen credenciales)

El resto del código solo llama a estas tres funciones; nunca importa un adaptador directo.
"""

from __future__ import annotations

import os
from datetime import date

from core.puertos import BancoPort, MercadoPort, Reloj

MODOS = ("fakes", "simulado", "api", "mcp")
_FECHA_INICIO_SIMULADO = date(2026, 11, 1)
_SQLITE_POR_DEFECTO = "banco/datos/registro.sqlite"


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

    from banco.reloj import RelojSimulado

    return RelojSimulado(_FECHA_INICIO_SIMULADO)


def obtener_mercado() -> MercadoPort:
    modo = modo_actual()
    if modo == "fakes":
        from fakes.fakes import MercadoFalso

        return MercadoFalso()

    from banco.mercado import MercadoSocrata

    return MercadoSocrata()


def obtener_banco(reloj: Reloj | None = None) -> BancoPort:
    modo = modo_actual()
    if modo == "fakes":
        from fakes.fakes import BancoFalso

        return BancoFalso()

    if modo == "simulado":
        from banco.registro import Registro
        from banco.simulado import BancoSimulado

        ruta_sqlite = (os.getenv("BANCO_SQLITE_PATH") or _SQLITE_POR_DEFECTO).strip() or _SQLITE_POR_DEFECTO
        return BancoSimulado(
            reloj or obtener_reloj(),
            mercado=obtener_mercado(),
            registro=Registro(ruta_sqlite),
        )

    if modo == "api":
        from banco.belo_api import BeloApiBanco

        banco = BeloApiBanco()
        if banco.esta_configurado():
            return banco
        raise _pendiente("api", "obtener_banco")

    from banco.belo_mcp import BeloMcpBanco

    banco = BeloMcpBanco()
    if banco.esta_configurado():
        return banco
    raise _pendiente("mcp", "obtener_banco")
