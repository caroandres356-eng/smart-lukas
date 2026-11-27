"""Adaptador de la API REST de Belo cumpliendo `BancoPort`.

Usa `BELO_API_URL` y `BELO_API_KEY` del `.env` (o parámetros explícitos) y cliente `httpx`.
Todo lo que devuelve lleva `fuente="belo"`. El dinero se convierte a `Decimal` sin pasar por `float`.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from core.modelos import Cotizacion, Moneda, Movimiento, Operacion, Rendimiento, Resultado, Saldo

PENDIENTE = "pendiente credenciales de Belo"

_ESTADOS_OK = frozenset({"completed", "ok", "executed"})
_ALIAS_TIPO_MOVIMIENTO: dict[str, str] = {
    "ingreso": "ingreso",
    "deposit": "ingreso",
    "income": "ingreso",
    "conversion": "conversion",
    "swap": "conversion",
    "exchange": "conversion",
    "pago": "pago",
    "payment": "pago",
    "transfer": "pago",
    "rendimiento": "rendimiento",
    "yield": "rendimiento",
    "interest": "rendimiento",
}
_SIN_VALOR = object()


def _limpiar(valor: str | None, *, quitar_barra: bool = False) -> str | None:
    if valor is None:
        return None
    limpio = valor.strip()
    if quitar_barra:
        limpio = limpio.rstrip("/")
    return limpio or None


def _a_decimal(valor: Any) -> Decimal:
    """Convierte un valor numérico o textual a `Decimal` sin pasar por `float`."""
    if isinstance(valor, Decimal):
        return valor
    if valor is None or isinstance(valor, bool):
        raise ValueError(f"Valor inválido para Decimal: {valor!r}")
    texto = str(valor).strip()
    if not texto:
        raise ValueError("Valor vacío para Decimal")
    try:
        return Decimal(texto)
    except InvalidOperation as exc:
        raise ValueError(f"Valor decimal inválido: {valor!r}") from exc


def _hoy_utc() -> date:
    return datetime.now(timezone.utc).date()


def _parsear_fecha(valor: Any, *, default_hoy: bool = False) -> date:
    """Convierte fecha o datetime ISO a `date` en UTC."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        if default_hoy:
            return _hoy_utc()
        raise ValueError("Fecha faltante en respuesta de Belo")
    if isinstance(valor, datetime):
        utc_dt = valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor.astimezone(timezone.utc)
        return utc_dt.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        texto = valor.strip()
        if "T" in texto or " " in texto or len(texto) > 10:
            dt = datetime.fromisoformat(texto.replace("Z", "+00:00"))
            utc_dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
            return utc_dt.date()
        return date.fromisoformat(texto[:10])
    raise ValueError(f"Formato de fecha inválido: {valor!r}")


def _decodificar_json(texto: str) -> Any:
    """Decodifica JSON preservando decimales directamente en `Decimal` (sin `float`)."""
    return json.loads(texto, parse_float=Decimal)


def _obtener_campo(datos: Mapping[str, Any], *claves: str, default: Any = _SIN_VALOR) -> Any:
    for clave in claves:
        if clave in datos and datos[clave] is not None:
            return datos[clave]
    if default is not _SIN_VALOR:
        return default
    raise KeyError(f"Falta alguno de los campos esperados {claves} en {dict(datos)!r}")


def _serializar_operacion(op: Operacion) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": op.id,
        "tipo": op.tipo,
        "desde": op.desde,
        "hacia": op.hacia,
        "monto": str(op.monto),
        "categoria": op.categoria,
        "fecha_programada": op.fecha_programada.isoformat(),
    }
    if op.mandato_id is not None:
        payload["mandato_id"] = op.mandato_id
    if op.mandato_firma is not None:
        payload["mandato_firma"] = op.mandato_firma
    return payload


def _parsear_saldos(datos: Any) -> list[Saldo]:
    items = datos.get("balances", []) if isinstance(datos, Mapping) else datos
    if not isinstance(items, list):
        raise ValueError(f"Respuesta de saldos inválida: {datos!r}")
    return [
        Saldo(
            moneda=_obtener_campo(item, "currency", "moneda"),
            monto=_a_decimal(_obtener_campo(item, "amount", "monto")),
            fuente="belo",
        )
        for item in items
    ]


def _parsear_cotizacion(datos: Any, *, desde: Moneda, hacia: Moneda) -> Cotizacion:
    if not isinstance(datos, Mapping):
        raise ValueError(f"Respuesta de cotización inválida: {datos!r}")
    cuerpo = datos["quote"] if "quote" in datos and isinstance(datos["quote"], Mapping) else datos
    return Cotizacion(
        desde=_obtener_campo(cuerpo, "from", "desde", default=desde),
        hacia=_obtener_campo(cuerpo, "to", "hacia", default=hacia),
        tasa=_a_decimal(_obtener_campo(cuerpo, "rate", "tasa")),
        spread=_a_decimal(_obtener_campo(cuerpo, "spread", default="0")),
        fecha=_parsear_fecha(_obtener_campo(cuerpo, "date", "fecha", default=None), default_hoy=True),
        fuente="belo",
    )


def _parsear_rendimiento(datos: Any, *, moneda: Moneda) -> Rendimiento:
    cuerpo = datos
    if isinstance(datos, Mapping) and "yields" in datos and isinstance(datos["yields"], list):
        cuerpo = datos["yields"]
    if isinstance(cuerpo, list):
        encontrado = next(
            (
                item
                for item in cuerpo
                if isinstance(item, Mapping) and _obtener_campo(item, "currency", "moneda", default=None) == moneda
            ),
            cuerpo[0] if cuerpo else None,
        )
        cuerpo = encontrado
    if not isinstance(cuerpo, Mapping):
        raise ValueError(f"Respuesta de rendimiento inválida: {datos!r}")
    return Rendimiento(
        moneda=_obtener_campo(cuerpo, "currency", "moneda", default=moneda),
        tasa_anual=_a_decimal(_obtener_campo(cuerpo, "annual_rate", "tasa_anual")),
        fuente="belo",
    )


def _parsear_resultado(datos: Any, operacion_id: str, *, forzar_error: bool = False) -> Resultado:
    cuerpo = datos if isinstance(datos, Mapping) else {}
    mensaje = str(_obtener_campo(cuerpo, "mensaje", "message", "detail", "error", default=""))
    if forzar_error:
        ok = False
        if not mensaje:
            mensaje = "Operación duplicada (idempotencia)"
    elif "ok" in cuerpo and cuerpo["ok"] is not None:
        ok = bool(cuerpo["ok"])
    elif "status" in cuerpo and cuerpo["status"] is not None:
        estado = str(cuerpo["status"]).strip().lower()
        ok = estado in _ESTADOS_OK
        if not mensaje:
            mensaje = str(cuerpo["status"])
    else:
        ok = True

    return Resultado(
        operacion_id=operacion_id,
        ok=ok,
        mensaje=mensaje,
        mandato_id=cuerpo.get("mandato_id"),
        mandato_verificado=cuerpo.get("mandato_verificado"),
    )


def _parsear_movimientos(datos: Any) -> list[Movimiento]:
    items = datos.get("transactions", []) if isinstance(datos, Mapping) else datos
    if not isinstance(items, list):
        raise ValueError(f"Respuesta de movimientos inválida: {datos!r}")

    movimientos: list[Movimiento] = []
    for item in items:
        if not isinstance(item, Mapping):
            raise ValueError(f"Movimiento inválido en respuesta: {item!r}")
        tipo_raw = str(_obtener_campo(item, "type", "tipo")).strip().lower()
        tipo = _ALIAS_TIPO_MOVIMIENTO.get(tipo_raw, tipo_raw)
        kwargs: dict[str, Any] = {
            "fecha": _parsear_fecha(_obtener_campo(item, "date", "fecha", "created_at")),
            "tipo": tipo,
            "moneda": _obtener_campo(item, "currency", "moneda"),
            "monto": _a_decimal(_obtener_campo(item, "amount", "monto")),
            "descripcion": str(_obtener_campo(item, "description", "descripcion", default="")),
        }
        item_id = _obtener_campo(item, "id", default=None)
        if item_id is not None and str(item_id).strip():
            kwargs["id"] = str(item_id)
        movimientos.append(Movimiento(**kwargs))

    movimientos.sort(key=lambda m: m.fecha)
    return movimientos


class BeloApiBanco:
    """Adaptador REST de Belo cumpliendo `BancoPort`.

    Variables de entorno soportadas cuando no se pasan al constructor:
    - `BELO_API_URL`: URL base de la API REST de Belo.
    - `BELO_API_KEY`: Llave/token de autenticación Bearer.
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.url: str | None = _limpiar(os.getenv("BELO_API_URL") if url is None else url, quitar_barra=True)
        self.api_key: str | None = _limpiar(os.getenv("BELO_API_KEY") if api_key is None else api_key)
        self._transport = transport
        self.timeout = timeout

    def esta_configurado(self) -> bool:
        """Retorna `True` si `url` y `api_key` están presentes y no vacíos."""
        return bool(self.url and self.api_key)

    def _cliente(self) -> httpx.Client:
        if not self.esta_configurado():
            raise NotImplementedError(PENDIENTE)
        return httpx.Client(
            base_url=self.url or "",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Accept": "application/json",
            },
            timeout=self.timeout,
            transport=self._transport,
        )

    def _get_json(self, ruta: str, params: dict[str, str] | None = None) -> Any:
        with self._cliente() as client:
            respuesta = client.get(ruta, params=params)
            respuesta.raise_for_status()
            return _decodificar_json(respuesta.text)

    def saldos(self) -> list[Saldo]:
        """Consulta saldos por moneda vía `GET /balances`."""
        return _parsear_saldos(self._get_json("/balances"))

    def cotizacion(self, desde: Moneda, hacia: Moneda) -> Cotizacion:
        """Obtiene cotización puntual vía `GET /quotes`."""
        datos = self._get_json("/quotes", params={"from": desde, "to": hacia})
        return _parsear_cotizacion(datos, desde=desde, hacia=hacia)

    def rendimiento(self, moneda: Moneda) -> Rendimiento:
        """Consulta rendimiento anual vía `GET /yields`."""
        datos = self._get_json("/yields", params={"currency": moneda})
        return _parsear_rendimiento(datos, moneda=moneda)

    def ejecutar(self, op: Operacion) -> Resultado:
        """Ejecuta una conversión o pago de forma idempotente vía `POST /transactions`."""
        payload = _serializar_operacion(op)
        with self._cliente() as client:
            respuesta = client.post(
                "/transactions",
                headers={"Idempotency-Key": op.id},
                json=payload,
            )

        if respuesta.status_code == 409:
            datos = _decodificar_json(respuesta.text) if respuesta.text.strip() else {}
            return _parsear_resultado(datos, op.id, forzar_error=True)

        respuesta.raise_for_status()
        datos = _decodificar_json(respuesta.text) if respuesta.text.strip() else {}
        return _parsear_resultado(datos, op.id)

    def movimientos(self) -> list[Movimiento]:
        """Lista el historial de movimientos ordenados cronológicamente."""
        return _parsear_movimientos(self._get_json("/transactions"))
