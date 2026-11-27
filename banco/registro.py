"""Registro persistente de operaciones en SQLite (Persona 1).

Sirve para la idempotencia entre reinicios y para la pantalla de Operaciones.
Tabla sugerida: operaciones(id TEXT PRIMARY KEY, json TEXT, ok INTEGER, mensaje TEXT, creada TEXT UTC).
Usar solo la librería estándar (sqlite3). El archivo *.sqlite está en .gitignore.
"""

from __future__ import annotations

from pathlib import Path

from core.modelos import Operacion, Resultado

P1 = "Persona 1 (banco): "


class Registro:
    def __init__(self, ruta_sqlite: str | Path) -> None:
        self.ruta_sqlite = Path(ruta_sqlite)

    def guardar(self, op: Operacion, resultado: Resultado) -> None:
        """Guarda la operación y su resultado. Un id repetido no se duplica."""
        raise NotImplementedError(P1 + "Registro.guardar")

    def ya_ejecutada(self, op_id: str) -> bool:
        """True si existe una operación con ese id y ok=True."""
        raise NotImplementedError(P1 + "Registro.ya_ejecutada")
