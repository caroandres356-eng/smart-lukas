"""Carga, guarda y modifica la política del usuario (Persona 2).

La política vive en motor/politica.yaml con campos planos iguales a core.modelos.Politica.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import yaml
from pydantic import ValidationError

from core.modelos import CambioPolitica, Politica

RUTA_POR_DEFECTO = Path(__file__).resolve().parent / "politica.yaml"


class PoliticaInvalida(ValueError):
    """La política del YAML no se puede usar (falta un campo o tiene un valor inválido)."""


def _explicar_errores(error: ValidationError) -> str:
    lineas = []
    for e in error.errors():
        campo = ".".join(str(p) for p in e["loc"]) or "(raíz)"
        if e["type"] == "missing":
            lineas.append(f"- falta el campo '{campo}'")
        else:
            lineas.append(f"- '{campo}' = {e.get('input')!r}: {e['msg']}")
    return "\n".join(lineas)


def cargar_politica(ruta: str | Path = RUTA_POR_DEFECTO) -> Politica:
    """Lee el YAML y lo valida con Politica. Si algo está mal lanza PoliticaInvalida con un mensaje claro."""
    ruta = Path(ruta)
    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    if not isinstance(datos, dict):
        raise PoliticaInvalida(f"La política en {ruta} está vacía o no tiene el formato 'campo: valor'.")
    try:
        return Politica.model_validate(datos)
    except ValidationError as e:
        raise PoliticaInvalida(f"La política en {ruta} no es válida:\n{_explicar_errores(e)}") from e


class _Dumper(yaml.SafeDumper):
    pass


def _representar_decimal(dumper: yaml.SafeDumper, valor: Decimal) -> yaml.Node:
    # Se escribe como número (no como texto) para que el YAML siga siendo legible.
    if valor == valor.to_integral_value():
        return dumper.represent_scalar("tag:yaml.org,2002:int", str(int(valor)))
    return dumper.represent_scalar("tag:yaml.org,2002:float", format(valor.normalize(), "f"))


_Dumper.add_representer(Decimal, _representar_decimal)


def guardar_politica(politica: Politica, ruta: str | Path = RUTA_POR_DEFECTO) -> None:
    """Escribe la política en YAML (Decimal como número, legible para humanos).
    cargar_politica(guardar_politica(p)) devuelve una política igual a p."""
    datos = politica.model_dump(mode="python")
    texto = yaml.dump(datos, Dumper=_Dumper, sort_keys=False, allow_unicode=True, default_flow_style=False)
    encabezado = "# Política del usuario. Los campos coinciden con core.modelos.Politica.\n"
    Path(ruta).write_text(encabezado + texto, encoding="utf-8")


def aplicar_cambio(politica: Politica, cambio: CambioPolitica) -> Politica:
    """Devuelve una NUEVA política con el cambio agregado a reglas_aprendidas (no muta la original).

    Si ya existe una regla para el mismo (tipo, categoria), la reemplaza:
    la última respuesta del usuario manda.
    """
    reglas = [
        r.model_copy()
        for r in politica.reglas_aprendidas
        if not (r.tipo == cambio.tipo and r.categoria == cambio.categoria)
    ]
    reglas.append(cambio.model_copy())
    return politica.model_copy(update={"reglas_aprendidas": reglas}, deep=True)
