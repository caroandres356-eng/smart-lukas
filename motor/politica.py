"""Carga, guarda y modifica la política del usuario (Persona 2).

La política vive en motor/politica.yaml con campos planos iguales a core.modelos.Politica.
"""

from __future__ import annotations

from pathlib import Path

from core.modelos import CambioPolitica, Politica

P2 = "Persona 2 (motor): "
RUTA_POR_DEFECTO = Path(__file__).resolve().parent / "politica.yaml"


def cargar_politica(ruta: str | Path = RUTA_POR_DEFECTO) -> Politica:
    """Lee el YAML y lo valida con Politica (los errores de validación se dejan subir)."""
    raise NotImplementedError(P2 + "cargar_politica")


def guardar_politica(politica: Politica, ruta: str | Path = RUTA_POR_DEFECTO) -> None:
    """Escribe la política en YAML (Decimal como número, legible para humanos).
    cargar_politica(guardar_politica(p)) debe devolver una política igual a p."""
    raise NotImplementedError(P2 + "guardar_politica")


def aplicar_cambio(politica: Politica, cambio: CambioPolitica) -> Politica:
    """Devuelve una NUEVA política con el cambio agregado a reglas_aprendidas (no muta la original).

    Si ya existe una regla para el mismo (tipo, categoria), la reemplaza:
    la última respuesta del usuario manda.
    """
    raise NotImplementedError(P2 + "aplicar_cambio")
