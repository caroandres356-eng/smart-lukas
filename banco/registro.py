"""Registro persistente de operaciones en SQLite (Persona 1).

Sirve para la idempotencia entre reinicios y para la pantalla de Operaciones.
Tabla: operaciones(id, json, ok, mensaje, creada, mandato_id, mandato_firma).
Usa solo la librería estándar (sqlite3). El archivo *.sqlite está en .gitignore.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.modelos import Operacion, Resultado

_COLUMNAS = "id, json, ok, mensaje, creada, mandato_id, mandato_firma"


def _fila_a_dict(fila: sqlite3.Row) -> dict[str, Any]:
    """Convierte una fila SQLite de operaciones a diccionario."""
    return {
        "id": fila["id"],
        "json": fila["json"],
        "ok": bool(fila["ok"]),
        "mensaje": fila["mensaje"],
        "creada": fila["creada"],
        "mandato_id": fila["mandato_id"],
        "mandato_firma": fila["mandato_firma"],
    }


class Registro:
    """Almacén SQLite seguro frente a concurrencia para operaciones ejecutadas."""

    def __init__(self, ruta_sqlite: str | Path = ":memory:") -> None:
        es_memoria = str(ruta_sqlite) == ":memory:"
        self.ruta_sqlite = Path(ruta_sqlite)
        if not es_memoria:
            self.ruta_sqlite.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        destino = ":memory:" if es_memoria else str(self.ruta_sqlite)
        self._conn = sqlite3.connect(destino, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock, self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS operaciones (
                    id TEXT PRIMARY KEY,
                    json TEXT NOT NULL,
                    ok INTEGER NOT NULL,
                    mensaje TEXT NOT NULL,
                    creada TEXT NOT NULL,
                    mandato_id TEXT,
                    mandato_firma TEXT
                )
                """
            )

    def guardar(self, op: Operacion, resultado: Resultado) -> None:
        """Guarda el resultado. Un éxito posterior actualiza un intento fallido previo."""
        creada_utc = datetime.now(timezone.utc).isoformat()
        mandato_id = op.mandato_id or resultado.mandato_id
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO operaciones (
                    id, json, ok, mensaje, creada, mandato_id, mandato_firma
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    json = excluded.json,
                    ok = excluded.ok,
                    mensaje = excluded.mensaje,
                    creada = excluded.creada,
                    mandato_id = excluded.mandato_id,
                    mandato_firma = excluded.mandato_firma
                WHERE operaciones.ok = 0 AND excluded.ok = 1
                """,
                (
                    op.id,
                    op.model_dump_json(),
                    1 if resultado.ok else 0,
                    resultado.mensaje,
                    creada_utc,
                    mandato_id,
                    op.mandato_firma,
                ),
            )

    def ya_ejecutada(self, op_id: str) -> bool:
        """Devuelve True solo si existe una fila con ese id y ok=1."""
        with self._lock:
            fila = self._conn.execute(
                "SELECT 1 FROM operaciones WHERE id = ? AND ok = 1 LIMIT 1",
                (op_id,),
            ).fetchone()
            return fila is not None

    def obtener(self, op_id: str) -> dict[str, Any] | None:
        """Obtiene el registro completo de una operación por su id, o None si no existe."""
        with self._lock:
            fila = self._conn.execute(
                f"SELECT {_COLUMNAS} FROM operaciones WHERE id = ?",
                (op_id,),
            ).fetchone()
            return _fila_a_dict(fila) if fila is not None else None

    def listar(self) -> list[dict[str, Any]]:
        """Lista todas las operaciones registradas en orden de inserción."""
        with self._lock:
            filas = self._conn.execute(
                f"SELECT {_COLUMNAS} FROM operaciones ORDER BY rowid ASC"
            ).fetchall()
            return [_fila_a_dict(fila) for fila in filas]

    def cerrar(self) -> None:
        """Cierra la conexión SQLite subyacente."""
        with self._lock:
            self._conn.close()
