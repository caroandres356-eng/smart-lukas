"""Mandatos criptográficos estilo AP2 (Idea 3 · Doble llave).

Implementa el esqueleto verificable de la arquitectura de mandatos inspirada en
`google-agentic-commerce/AP2`:
- `IntentMandate`: límites y reglas de la política vigente.
- `QuoteMandate`: cotización comprometida con vigencia acotada.
- `PaymentMandate`: autorización firmada con HMAC-SHA256 para una `Operacion` puntual.

La verificación es estrictamente fail-closed: cualquier discrepancia de firma,
expiración o campos de la operación devuelve `False`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from core.modelos import Moneda, Operacion, nuevo_id

AprobacionMandato = Literal["auto_politica", "humana_solo_esta_vez", "humana_siempre"]

# Secreto efímero de proceso usado solo en desarrollo cuando MANDATO_SECRET_KEY está vacío.
_SECRETO_EFIMERO_DEV: bytes = secrets.token_bytes(32)


def _a_utc(valor: datetime) -> datetime:
    """Normaliza un datetime a UTC (si carece de zona horaria se asume UTC)."""
    if valor.tzinfo is None:
        return valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(timezone.utc)


class _BaseMandato(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IntentMandate(_BaseMandato):
    """Mandato de intención que captura los límites de la política del usuario."""

    id: str = Field(default_factory=nuevo_id)
    politica_hash: str
    max_usd_operacion: Decimal = Field(ge=0)
    max_usd_dia: Decimal = Field(ge=0)
    categorias_bloqueadas: list[str] = Field(default_factory=list)
    creado: datetime
    expira: datetime

    @field_validator("creado", "expira")
    @classmethod
    def _normalizar_utc(cls, valor: datetime) -> datetime:
        return _a_utc(valor)


class QuoteMandate(_BaseMandato):
    """Mandato de cotización que fija tasa y spread comprometidos antes de ejecutar."""

    id: str = Field(default_factory=nuevo_id)
    desde: Moneda
    hacia: Moneda
    tasa: Decimal = Field(gt=0)
    spread: Decimal = Field(ge=0, lt=1)
    cotizado_en: datetime
    expira: datetime

    @field_validator("cotizado_en", "expira")
    @classmethod
    def _normalizar_utc(cls, valor: datetime) -> datetime:
        return _a_utc(valor)


class PaymentMandate(_BaseMandato):
    """Mandato de pago firmado (doble llave: intención + aprobación/cotización)."""

    id: str = Field(default_factory=nuevo_id)
    operacion_id: str
    intent_hash: str
    quote_hash: Optional[str] = None
    monto: Decimal = Field(gt=0)
    moneda: Moneda
    aprobacion: AprobacionMandato
    solicitud_id: Optional[str] = None
    emitido_en: datetime
    expira: datetime
    firma: str = ""

    @field_validator("emitido_en", "expira")
    @classmethod
    def _normalizar_utc(cls, valor: datetime) -> datetime:
        return _a_utc(valor)


@runtime_checkable
class MandatoPort(Protocol):
    """Puerto para emisión y verificación de mandatos de pago AP2."""

    def emitir(
        self,
        operacion: Operacion,
        intent: IntentMandate | str,
        *,
        quote: QuoteMandate | str | None = None,
        aprobacion: AprobacionMandato = "auto_politica",
        solicitud_id: Optional[str] = None,
        emitido_en: Optional[datetime] = None,
        ttl_segundos: int = 300,
        expira: Optional[datetime] = None,
    ) -> PaymentMandate:
        """Emite y firma un `PaymentMandate` vinculado a la operación."""
        ...

    def verificar(self, mandato: PaymentMandate, ahora: datetime, operacion: Operacion) -> bool:
        """Verifica firma HMAC, expiración y coincidencia con la operación."""
        ...


def _resolver_secreto(secret_key: str | bytes | None = None) -> bytes:
    """Resuelve la clave HMAC desde argumento, `MANDATO_SECRET_KEY` o secreto efímero."""
    if secret_key is None:
        env_val = os.getenv("MANDATO_SECRET_KEY", "").strip()
        return env_val.encode("utf-8") if env_val else _SECRETO_EFIMERO_DEV
    if isinstance(secret_key, bytes):
        return secret_key if secret_key else _SECRETO_EFIMERO_DEV
    limpia = secret_key.strip()
    return limpia.encode("utf-8") if limpia else _SECRETO_EFIMERO_DEV


def _json_canonico(modelo: BaseModel, *, excluir: set[str] | None = None) -> bytes:
    """Serializa un modelo Pydantic de manera determinista (UTF-8, claves ordenadas)."""
    datos = modelo.model_dump(mode="json", exclude=excluir or set())
    return json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def hash_canonico(modelo: BaseModel) -> str:
    """Retorna el SHA-256 hexadecimal canónico de cualquier modelo Pydantic."""
    return hashlib.sha256(_json_canonico(modelo)).hexdigest()


def _firmar_payload(mandato: PaymentMandate, secreto: bytes) -> str:
    """Calcula la firma HMAC-SHA256 del `PaymentMandate` excluyendo el campo `firma`."""
    payload = _json_canonico(mandato, excluir={"firma"})
    return hmac.new(secreto, payload, hashlib.sha256).hexdigest()


class FirmadorMandatosAP2:
    """Implementación MVP de `MandatoPort` usando HMAC-SHA256 (stdlib)."""

    def __init__(self, secret_key: str | bytes | None = None) -> None:
        self._secreto = _resolver_secreto(secret_key)

    @staticmethod
    def hash_canonico(modelo: BaseModel) -> str:
        """Calcula el hash canónico SHA-256 de un modelo Pydantic."""
        return hash_canonico(modelo)

    def emitir(
        self,
        operacion: Operacion,
        intent: IntentMandate | str,
        *,
        quote: QuoteMandate | str | None = None,
        aprobacion: AprobacionMandato = "auto_politica",
        solicitud_id: Optional[str] = None,
        emitido_en: Optional[datetime] = None,
        ttl_segundos: int = 300,
        expira: Optional[datetime] = None,
    ) -> PaymentMandate:
        """Emite un `PaymentMandate` firmado para la `operacion` dada."""
        intent_hash = intent if isinstance(intent, str) else hash_canonico(intent)
        quote_hash = None if quote is None else (quote if isinstance(quote, str) else hash_canonico(quote))

        base_emitido = _a_utc(emitido_en) if emitido_en is not None else datetime.now(timezone.utc)
        fecha_expira = _a_utc(expira) if expira is not None else base_emitido + timedelta(seconds=ttl_segundos)

        mandato_base = PaymentMandate(
            operacion_id=operacion.id,
            intent_hash=intent_hash,
            quote_hash=quote_hash,
            monto=operacion.monto,
            moneda=operacion.desde,
            aprobacion=aprobacion,
            solicitud_id=solicitud_id,
            emitido_en=base_emitido,
            expira=fecha_expira,
            firma="",
        )
        firma = _firmar_payload(mandato_base, self._secreto)
        return mandato_base.model_copy(update={"firma": firma})

    def verificar(self, mandato: PaymentMandate, ahora: datetime, operacion: Operacion) -> bool:
        """Verifica de forma fail-closed firma HMAC, expiración y datos de la operación."""
        if not mandato.firma:
            return False

        ahora_utc = _a_utc(ahora)
        if ahora_utc >= _a_utc(mandato.expira):
            return False

        if mandato.operacion_id != operacion.id:
            return False
        if mandato.monto != operacion.monto:
            return False
        if mandato.moneda != operacion.desde:
            return False

        if operacion.mandato_id is not None and operacion.mandato_id != mandato.id:
            return False
        if operacion.mandato_firma is not None and not hmac.compare_digest(
            operacion.mandato_firma, mandato.firma
        ):
            return False

        firma_esperada = _firmar_payload(mandato, self._secreto)
        return hmac.compare_digest(firma_esperada, mandato.firma)


def emitir_payment_mandate(
    operacion: Operacion,
    intent: IntentMandate | str,
    *,
    quote: QuoteMandate | str | None = None,
    aprobacion: AprobacionMandato = "auto_politica",
    solicitud_id: Optional[str] = None,
    emitido_en: Optional[datetime] = None,
    ttl_segundos: int = 300,
    expira: Optional[datetime] = None,
    secret_key: str | bytes | None = None,
) -> PaymentMandate:
    """Atajo funcional para emitir y firmar un `PaymentMandate`."""
    return FirmadorMandatosAP2(secret_key=secret_key).emitir(
        operacion,
        intent,
        quote=quote,
        aprobacion=aprobacion,
        solicitud_id=solicitud_id,
        emitido_en=emitido_en,
        ttl_segundos=ttl_segundos,
        expira=expira,
    )


def verificar_mandato(
    mandato: PaymentMandate,
    ahora: datetime,
    operacion: Operacion,
    *,
    secret_key: str | bytes | None = None,
) -> bool:
    """Atajo funcional fail-closed para verificar un `PaymentMandate`."""
    return FirmadorMandatosAP2(secret_key=secret_key).verificar(mandato, ahora, operacion)
