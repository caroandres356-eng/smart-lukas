"""El Auditor Rojo: suite de tortura adversaria para agentes bancarios y MCP."""

from __future__ import annotations

from auditor_rojo.corredor import CorredorAuditorRojo, ObjetivoContratoBase, ObjetivoSimuladoDefensivo
from auditor_rojo.escenarios import generar_escenarios
from auditor_rojo.puertos import (
    CATEGORIAS_ATAQUE,
    AgenteAuditablePort,
    CategoriaAtaque,
    EscenarioAdversario,
    ReporteAuditoria,
    ResultadoEscenario,
)
from auditor_rojo.reporte import construir_reporte, renderizar_markdown

__all__ = [
    "AgenteAuditablePort",
    "CATEGORIAS_ATAQUE",
    "CategoriaAtaque",
    "CorredorAuditorRojo",
    "EscenarioAdversario",
    "ObjetivoContratoBase",
    "ReporteAuditoria",
    "ResultadoEscenario",
    "construir_reporte",
    "generar_escenarios",
    "renderizar_markdown",
]
