"""Puertos y modelos de contrato para El Auditor Rojo.

Define las interfaces (`AgenteAuditablePort`) y los modelos Pydantic v2
inmutables respecto a campos extra (`extra="forbid"`) para escenarios
adversarios, resultados individuales y reportes agregados de auditoría.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

CategoriaAtaque = Literal[
    "prompt_injection",
    "cobro_duplicado",
    "race_condition",
    "flash_fx",
    "aprobacion_expirada",
    "fuera_de_politica_persuasivo",
]

CATEGORIAS_ATAQUE: tuple[CategoriaAtaque, ...] = (
    "prompt_injection",
    "cobro_duplicado",
    "race_condition",
    "flash_fx",
    "aprobacion_expirada",
    "fuera_de_politica_persuasivo",
)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EscenarioAdversario(_Base):
    """Caso de prueba adversario dirigido a un agente bancario/MCP."""

    id: str = Field(min_length=1)
    categoria: CategoriaAtaque
    nombre: str = Field(min_length=1)
    descripcion: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)
    debe_bloquearse: bool = True


class ResultadoEscenario(_Base):
    """Resultado de ejecutar un `EscenarioAdversario` contra un objetivo."""

    escenario_id: str = Field(min_length=1)
    categoria: CategoriaAtaque
    bloqueado: bool
    motivo: str
    paso: bool


class ReporteAuditoria(_Base):
    """Resumen cuantitativo y detallado de una corrida de El Auditor Rojo."""

    total: int = Field(ge=0)
    pasados: int = Field(ge=0)
    fallados: int = Field(ge=0)
    tasa_exito: Decimal = Field(
        ge=Decimal("0"),
        le=Decimal("1"),
        description="Fracción de éxito entre 0 y 1 (pasados / total).",
    )
    por_categoria: dict[str, dict[str, int]] = Field(default_factory=dict)
    resultados: list[ResultadoEscenario] = Field(default_factory=list)


@runtime_checkable
class AgenteAuditablePort(Protocol):
    """Puerto que debe implementar cualquier agente o adaptador auditable."""

    def ejecutar_escenario(self, escenario: EscenarioAdversario) -> ResultadoEscenario:
        """Ejecuta un escenario adversario y reporta si fue bloqueado."""
        ...
