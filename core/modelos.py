"""Contrato de datos compartido por todo el equipo.

REGLAS DEL CONTRATO (nadie las rompe sin avisar):
- Solo se AGREGAN campos. Nunca se borran ni se renombran.
- El dinero SIEMPRE es Decimal (nunca float).
- Toda fecha/hora es UTC. Los datetime sin zona horaria se asumen UTC.
- Todo dato que venga de un banco o mercado dice de dónde viene (campo `fuente`).
- Los porcentajes tienen dos formatos, documentados en cada campo:
    * fracción (0.01 = 1 %): spread, tasa_anual
    * puntos porcentuales (15 = 15 %): Politica.impuestos_pct
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

Moneda = Literal["USD", "COP", "USDT"]
Fuente = Literal["simulado", "belo"]


def nuevo_id() -> str:
    """Id único corto (uuid4 en hex, 12 caracteres)."""
    return uuid.uuid4().hex[:12]


def _a_utc(valor: datetime) -> datetime:
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --------------------------------------------------------------------------- banco


class Saldo(_Base):
    moneda: Moneda
    monto: Decimal
    fuente: Fuente


class Cotizacion(_Base):
    desde: Moneda
    hacia: Moneda
    tasa: Decimal = Field(gt=0, description="Tasa de mercado SIN spread (ej. TRM).")
    spread: Decimal = Field(ge=0, lt=1, description="Fracción: 0.01 = 1 %.")
    fecha: date
    fuente: Fuente


class Rendimiento(_Base):
    moneda: Moneda
    tasa_anual: Decimal = Field(ge=0, description="Fracción: 0.10 = 10 % anual.")
    fuente: Fuente


class Movimiento(_Base):
    id: str = Field(default_factory=nuevo_id)
    fecha: date
    tipo: Literal["ingreso", "conversion", "pago", "rendimiento"]
    moneda: Moneda
    monto: Decimal
    descripcion: str = ""


class Operacion(_Base):
    """Una orden que el agente quiere ejecutar en el banco.

    `id` sirve para idempotencia: ejecutar dos veces el mismo id no repite la operación.
    `monto` está expresado en la moneda `desde`.
    """

    id: str = Field(default_factory=nuevo_id)
    tipo: Literal["conversion", "pago"]
    desde: Moneda
    hacia: Optional[Moneda] = None
    monto: Decimal = Field(gt=0)
    categoria: str = Field(description='"arriendo", "internet", "ahorro", "impuestos", ...')
    fecha_programada: date


class Resultado(_Base):
    operacion_id: str
    ok: bool
    mensaje: str = ""


# --------------------------------------------------------------------------- motor


class Ruta(_Base):
    nombre: str
    descripcion: str
    operaciones: list[Operacion] = Field(default_factory=list)
    cop_final: Decimal


class Veredicto(_Base):
    operacion: Operacion
    estado: Literal["auto", "requiere_aprobacion", "bloqueada"]
    motivo: str = Field(description="Siempre dice la regla y los números.")


class Propuesta(_Base):
    id: str = Field(default_factory=nuevo_id)
    ingreso: Movimiento
    rutas: list[Ruta]
    elegida: str = Field(description="Nombre de la ruta elegida.")
    veredictos: list[Veredicto] = Field(default_factory=list)
    ahorro_cop: Decimal = Field(
        description='cop_final(elegida) - cop_final("Todo hoy").'
    )

    def ruta_elegida(self) -> Ruta:
        for ruta in self.rutas:
            if ruta.nombre == self.elegida:
                return ruta
        raise ValueError(f"La ruta elegida '{self.elegida}' no está en rutas")


# --------------------------------------------------------------------------- aprobaciones


class Solicitud(_Base):
    id: str = Field(default_factory=nuevo_id)
    operacion: Operacion
    motivo: str
    creada: datetime
    vence: datetime
    estado: Literal["pendiente", "en_cola", "aprobada", "rechazada", "vencida"]

    @field_validator("creada", "vence")
    @classmethod
    def _utc(cls, valor: datetime) -> datetime:
        return _a_utc(valor)


class CambioPolitica(_Base):
    """Lo que aprende el agente cuando el usuario responde "Siempre" o "Nunca"."""

    accion: Literal["permitir_hasta", "bloquear"]
    tipo: Literal["conversion", "pago"]
    categoria: str
    monto_max_usd: Optional[Decimal] = Field(default=None, ge=0)


# --------------------------------------------------------------------------- política


class GastoFijo(_Base):
    nombre: str
    monto_cop: Decimal = Field(ge=0)
    dia: int = Field(ge=1, le=31)


class Politica(_Base):
    auto_max_usd_por_operacion: Decimal = Field(ge=0)
    auto_max_usd_por_dia: Decimal = Field(ge=0)
    impuestos_pct: Decimal = Field(ge=0, le=100, description="Puntos: 15 = 15 %.")
    colchon_usd: Decimal = Field(ge=0)
    gastos_fijos: list[GastoFijo] = Field(default_factory=list)
    vence_en_segundos: int = Field(ge=0)
    max_interrupciones_dia: int = Field(ge=0)
    reglas_aprendidas: list[CambioPolitica] = Field(default_factory=list)
