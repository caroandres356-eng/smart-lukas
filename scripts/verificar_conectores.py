"""Diagnóstico de conectores del entorno smart-lukas.

Función principal::

    diagnosticar_entorno() -> dict[str, dict]

Cada conector devuelve::

    {
        "configurado": bool,
        "descripcion": str,
        "pendiente": str | None,  # None si está configurado
    }

CLI::

    python scripts/verificar_conectores.py
    python scripts/verificar_conectores.py --live   # intenta llamadas de red reales
"""

from __future__ import annotations

import os
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

ConectorInfo = dict[str, Any]
DiagnosticoCompleto = dict[str, ConectorInfo]


# ---------------------------------------------------------------------------
# Verificadores individuales (sin red por defecto)
# ---------------------------------------------------------------------------


def _banco_modo() -> ConectorInfo:
    """Inspecciona `BANCO_MODO` según los modos admitidos por la fábrica."""
    valor = os.getenv("BANCO_MODO", "fakes").strip().lower() or "fakes"
    modos_validos = {"fakes", "simulado", "api", "mcp"}
    configurado = valor in modos_validos
    return {
        "configurado": configurado,
        "descripcion": f"BANCO_MODO={valor!r}",
        "pendiente": None if configurado else "Elegir BANCO_MODO=fakes, simulado, api o mcp.",
    }


def _socrata_app_token() -> ConectorInfo:
    """Inspecciona `SOCRATA_APP_TOKEN` (TRM Dane/Datos Colombia)."""
    valor = os.getenv("SOCRATA_APP_TOKEN", "").strip()
    configurado = bool(valor)
    return {
        "configurado": configurado,
        "descripcion": "SOCRATA_APP_TOKEN detectado." if configurado else "SOCRATA_APP_TOKEN no definida.",
        "pendiente": (
            None
            if configurado
            else "Registrarse en data.gov.co y exportar SOCRATA_APP_TOKEN en el .env."
        ),
    }


def _mandato_secret_key() -> ConectorInfo:
    """Inspecciona `MANDATO_SECRET_KEY` (HMAC-SHA256 para mandatos AP2)."""
    valor = os.getenv("MANDATO_SECRET_KEY", "").strip()
    configurado = bool(valor)
    return {
        "configurado": configurado,
        "descripcion": (
            f"MANDATO_SECRET_KEY detectada ({len(valor)} bytes)."
            if configurado
            else "MANDATO_SECRET_KEY no definida (se usa secreto efímero de proceso)."
        ),
        "pendiente": (
            None
            if configurado
            else "Generar con `python -c 'import secrets; print(secrets.token_hex(32))'` y exportar en .env."
        ),
    }


def _deepseek_api_key() -> ConectorInfo:
    """Inspecciona `DEEPSEEK_API_KEY`."""
    valor = os.getenv("DEEPSEEK_API_KEY", "").strip()
    configurado = bool(valor)
    return {
        "configurado": configurado,
        "descripcion": "DEEPSEEK_API_KEY detectada." if configurado else "DEEPSEEK_API_KEY no definida.",
        "pendiente": (
            None
            if configurado
            else "Crear cuenta en platform.deepseek.com y exportar DEEPSEEK_API_KEY en el .env."
        ),
    }


def _belo_api() -> ConectorInfo:
    """Inspecciona `BELO_API_URL` y `BELO_API_KEY`."""
    url = os.getenv("BELO_API_URL", "").strip()
    key = os.getenv("BELO_API_KEY", "").strip()
    configurado = bool(url) and bool(key)
    partes: list[str] = []
    pendientes: list[str] = []
    if url:
        partes.append(f"BELO_API_URL={url!r}")
    else:
        pendientes.append("Definir BELO_API_URL (ej. https://api.belo.app).")
    if key:
        partes.append("BELO_API_KEY detectada.")
    else:
        pendientes.append("Definir BELO_API_KEY con el token de la cuenta Belo.")
    return {
        "configurado": configurado,
        "descripcion": " | ".join(partes) if partes else "BELO_API_URL y BELO_API_KEY no definidas.",
        "pendiente": " ".join(pendientes) if pendientes else None,
    }


def _belo_mcp() -> ConectorInfo:
    """Inspecciona `BELO_MCP_URL`."""
    url = os.getenv("BELO_MCP_URL", "").strip()
    configurado = bool(url)
    return {
        "configurado": configurado,
        "descripcion": f"BELO_MCP_URL={url!r}" if configurado else "BELO_MCP_URL no definida.",
        "pendiente": (
            None
            if configurado
            else "Definir BELO_MCP_URL apuntando al servidor MCP de Belo (ej. http://localhost:8000/mcp)."
        ),
    }


# ---------------------------------------------------------------------------
# Verificación con red (--live)
# ---------------------------------------------------------------------------


def _verificar_deepseek_live() -> ConectorInfo:
    """Intenta una llamada real a DeepSeek (solo con --live)."""
    info = _deepseek_api_key()
    if not info["configurado"]:
        return info
    try:
        import httpx  # noqa: PLC0415

        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        url = f"{base_url}/v1/models"
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {api_key}"})
        if resp.status_code == 200:
            info["descripcion"] += " — ping OK (live)."
        else:
            info["descripcion"] += f" — ping falló: HTTP {resp.status_code}."
            info["pendiente"] = f"Verificar que DEEPSEEK_API_KEY sea válida. HTTP {resp.status_code}."
            info["configurado"] = False
    except Exception as exc:  # noqa: BLE001
        info["descripcion"] += f" — error de red: {exc}."
        info["pendiente"] = str(exc)
        info["configurado"] = False
    return info


def _verificar_belo_live() -> ConectorInfo:
    """Intenta una llamada real a Belo API (solo con --live)."""
    info = _belo_api()
    if not info["configurado"]:
        return info
    try:
        import httpx  # noqa: PLC0415

        url = os.getenv("BELO_API_URL", "").rstrip("/") + "/health"
        key = os.getenv("BELO_API_KEY", "")
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {key}"})
        if resp.status_code < 400:
            info["descripcion"] += " — ping OK (live)."
        else:
            info["descripcion"] += f" — ping falló: HTTP {resp.status_code}."
            info["pendiente"] = f"HTTP {resp.status_code}."
            info["configurado"] = False
    except Exception as exc:  # noqa: BLE001
        info["descripcion"] += f" — error de red: {exc}."
        info["pendiente"] = str(exc)
        info["configurado"] = False
    return info


# ---------------------------------------------------------------------------
# Función pública principal
# ---------------------------------------------------------------------------


def diagnosticar_entorno(*, live: bool = False) -> DiagnosticoCompleto:
    """Inspecciona el estado de los conectores del entorno.

    Parámetros
    ----------
    live:
        Si es ``True``, intenta llamadas de red reales para validar las
        credenciales; por defecto solo revisa variables de entorno.

    Retorna
    -------
    dict[str, dict]
        Mapa ``{nombre_conector: {"configurado": bool, "descripcion": str, "pendiente": str | None}}``.
    """
    resultado: DiagnosticoCompleto = {
        "BANCO_MODO": _banco_modo(),
        "SOCRATA_APP_TOKEN": _socrata_app_token(),
        "MANDATO_SECRET_KEY": _mandato_secret_key(),
        "DEEPSEEK_API_KEY": _verificar_deepseek_live() if live else _deepseek_api_key(),
        "BELO_API": _verificar_belo_live() if live else _belo_api(),
        "BELO_MCP_URL": _belo_mcp(),
    }
    return resultado


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _imprimir_tabla(diagnostico: DiagnosticoCompleto) -> None:
    """Imprime una tabla legible con el estado de cada conector."""
    anchos = {
        "conector": max(len(k) for k in diagnostico) + 2,
        "estado": 12,
        "descripcion": 55,
        "pendiente": 45,
    }

    def _fila(*celdas: str) -> str:
        c, e, d, p = celdas
        return f"  {c:<{anchos['conector']}}  {e:<{anchos['estado']}}  {d:<{anchos['descripcion']}}  {p}"

    sep = "-" * (anchos["conector"] + anchos["estado"] + anchos["descripcion"] + anchos["pendiente"] + 10)
    print()
    print("  🔍  Diagnóstico de conectores — smart-lukas")
    print(sep)
    print(_fila("CONECTOR", "ESTADO", "DESCRIPCIÓN", "PENDIENTE"))
    print(sep)
    for nombre, info in diagnostico.items():
        estado = "✅ OK" if info["configurado"] else "❌ falta"
        descripcion = str(info.get("descripcion", ""))[:anchos["descripcion"]]
        pendiente = str(info.get("pendiente") or "—")[:anchos["pendiente"]]
        print(_fila(nombre, estado, descripcion, pendiente))
    print(sep)
    total = len(diagnostico)
    ok = sum(1 for i in diagnostico.values() if i["configurado"])
    print(f"\n  {ok}/{total} conectores configurados.\n")


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI."""
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(
        prog="verificar_conectores",
        description="Diagnóstico de conectores de entorno para smart-lukas.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        default=False,
        help="Realiza llamadas de red reales para validar credenciales.",
    )
    args = parser.parse_args(argv)

    diagnostico = diagnosticar_entorno(live=args.live)
    _imprimir_tabla(diagnostico)
    # Código de salida: 0 si todos están OK, 1 si hay alguno sin configurar.
    todos_ok = all(i["configurado"] for i in diagnostico.values())
    return 0 if todos_ok else 1


if __name__ == "__main__":
    sys.exit(main())
