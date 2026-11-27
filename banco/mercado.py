"""Mercado con TRM real vía API Socrata de datos.gov.co. Cumple core.puertos.MercadoPort.

Consulta la API SODA2 de datos abiertos de Colombia para obtener la TRM histórica,
guarda una caché local en JSON y aplica fallbacks en orden:
1. API Socrata (`datos.gov.co`) o caché en memoria de la instancia.
2. Caché JSON local (`SOCRATA_CACHE_PATH`, por defecto `banco/datos/trm_cache.json`).
3. CSV local (`banco/datos/trm.csv`) con columnas `valor` y `vigenciadesde`.
4. Fixtures sintéticos (`fixtures/cotizaciones_30d.json`) vía `fakes.cargar_cotizaciones_ejemplo()`.

Las cotizaciones van SIN spread en `tasa`, con `spread=0.01` y `fuente="simulado"`.
"""

from __future__ import annotations

import csv
import json
import os
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from core.modelos import Cotizacion, Moneda
from fakes.fakes import cargar_cotizaciones_ejemplo

SPREAD_POR_DEFECTO = Decimal("0.01")
DATASET_POR_DEFECTO = "32sa-8pi3"
CACHE_POR_DEFECTO = "banco/datos/trm_cache.json"
URL_SOCRATA = "https://www.datos.gov.co/resource/{dataset_id}.json"


def _parsear_fecha(valor: str) -> date:
    """Convierte fechas ISO (con o sin hora) o DD/MM/YYYY a `date`."""
    texto = valor.strip()
    if not texto:
        raise ValueError("Fecha vacía en dato de TRM")
    if "T" in texto:
        return datetime.fromisoformat(texto.replace("Z", "+00:00")).date()
    if "/" in texto:
        return datetime.strptime(texto[:10], "%d/%m/%Y").date()
    return date.fromisoformat(texto[:10])


def _parsear_decimal(valor: Any) -> Decimal:
    """Convierte el valor TRM a `Decimal`."""
    texto = str(valor).strip().replace(",", "")
    if not texto:
        raise ValueError("Valor TRM vacío")
    return Decimal(texto)


class MercadoSocrata:
    """Adaptador de mercado TRM conectado a la API Socrata (SODA2) con fallbacks locales."""

    def __init__(
        self,
        ruta_csv: str | Path = "banco/datos/trm.csv",
        *,
        ruta_cache: str | Path | None = None,
        app_token: str | None = None,
        dataset_id: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.ruta_csv = Path(ruta_csv)
        cache_env = os.getenv("SOCRATA_CACHE_PATH") or CACHE_POR_DEFECTO
        self.ruta_cache = Path(ruta_cache) if ruta_cache is not None else Path(cache_env)

        token = app_token if app_token is not None else os.getenv("SOCRATA_APP_TOKEN")
        self.app_token = token.strip() if token and token.strip() else None

        dataset = dataset_id if dataset_id is not None else os.getenv("SOCRATA_DATASET_ID")
        self.dataset_id = dataset.strip() if dataset and dataset.strip() else DATASET_POR_DEFECTO

        self._transport = transport
        self._cache_memoria: list[Cotizacion] | None = None
        self._socrata_consultado = False
        self._limite_socrata = 0

    @staticmethod
    def _validar_par(desde: Moneda, hacia: Moneda) -> None:
        if desde != "USD" or hacia != "COP":
            raise ValueError(f"MercadoSocrata solo soporta USD->COP (recibido {desde}->{hacia})")

    def extraer_socrata(self, dias: int = 30, hasta: date | None = None) -> list[Cotizacion]:
        """Consulta la API Socrata de `datos.gov.co`, ordena de más antigua a más reciente y guarda caché."""
        url = URL_SOCRATA.format(dataset_id=self.dataset_id)
        limite = max(dias * 2, 60)
        params: dict[str, str | int] = {
            "$order": "vigenciadesde DESC",
            "$limit": limite,
        }
        if hasta is not None:
            params["$where"] = f"vigenciadesde <= '{hasta.isoformat()}T23:59:59'"

        headers = {"X-App-Token": self.app_token} if self.app_token else {}

        with httpx.Client(timeout=10.0, transport=self._transport) as client:
            respuesta = client.get(url, params=params, headers=headers)
            respuesta.raise_for_status()
            datos = respuesta.json()

        cotizaciones = self._parsear_socrata(datos)
        if cotizaciones:
            self._guardar_cache(cotizaciones)
            if hasta is None:
                self._cache_memoria = cotizaciones
                self._socrata_consultado = True
                self._limite_socrata = limite
        return cotizaciones

    def historico(self, desde: Moneda, hacia: Moneda, dias: int) -> list[Cotizacion]:
        """Últimas `dias` cotizaciones (de la más antigua a la más reciente)."""
        self._validar_par(desde, hacia)
        if dias <= 0:
            return []
        serie = self._obtener_serie(dias)
        return serie[-dias:]

    def cotizacion_para_fecha(
        self,
        fecha: date,
        desde: Moneda = "USD",
        hacia: Moneda = "COP",
    ) -> Cotizacion:
        """Devuelve la cotización vigente para `fecha`.

        Busca en las cotizaciones cargadas la publicación más reciente con `c.fecha <= fecha`
        (clave para fines de semana y festivos sin publicación diaria en Socrata).
        Si `fecha` es anterior a todas las disponibles, usa la tasa más antigua disponible.
        En ambos casos devuelve una `Cotizacion` válida con `fecha=fecha`.
        """
        self._validar_par(desde, hacia)
        if isinstance(fecha, datetime):
            fecha = fecha.date()

        serie = self._obtener_serie(dias=30)
        if not serie:
            raise ValueError("No hay cotizaciones disponibles para resolver la fecha")

        elegida = serie[0]
        for cotizacion in serie:
            if cotizacion.fecha <= fecha:
                elegida = cotizacion
            else:
                break

        if elegida.fecha == fecha:
            return elegida
        return elegida.model_copy(update={"fecha": fecha})

    def _obtener_serie(self, dias: int) -> list[Cotizacion]:
        limite_necesario = max(dias * 2, 60)
        if self._cache_memoria is not None:
            puede_pedir_mas = (
                self._socrata_consultado
                and limite_necesario > self._limite_socrata
                and len(self._cache_memoria) >= self._limite_socrata
            )
            if not puede_pedir_mas:
                return self._cache_memoria

        try:
            cotizaciones = self.extraer_socrata(dias=dias)
            if cotizaciones:
                return cotizaciones
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            pass

        for cargador in (self._leer_cache, self._leer_csv, self._leer_fixtures):
            cotizaciones = cargador()
            if cotizaciones:
                self._cache_memoria = cotizaciones
                return cotizaciones

        return []

    def _parsear_socrata(self, datos: Any) -> list[Cotizacion]:
        if not isinstance(datos, list):
            raise ValueError("Respuesta Socrata inesperada: se esperaba una lista JSON")

        cotizaciones: list[Cotizacion] = []
        for item in datos:
            if not isinstance(item, dict):
                raise ValueError("Elemento inválido en respuesta Socrata")
            _ = item.get("vigenciahasta")
            cotizaciones.append(
                Cotizacion(
                    desde="USD",
                    hacia="COP",
                    tasa=_parsear_decimal(item["valor"]),
                    spread=SPREAD_POR_DEFECTO,
                    fecha=_parsear_fecha(str(item["vigenciadesde"])),
                    fuente="simulado",
                )
            )
        return sorted(cotizaciones, key=lambda c: c.fecha)

    def _guardar_cache(self, cotizaciones: list[Cotizacion]) -> None:
        self.ruta_cache.parent.mkdir(parents=True, exist_ok=True)
        contenido = json.dumps(
            [c.model_dump(mode="json") for c in cotizaciones],
            indent=2,
            ensure_ascii=False,
        )
        self.ruta_cache.write_text(contenido, encoding="utf-8")

    def _leer_cache(self) -> list[Cotizacion]:
        if not self.ruta_cache.exists():
            return []
        try:
            datos = json.loads(self.ruta_cache.read_text(encoding="utf-8"))
            if not isinstance(datos, list):
                return []
            cotizaciones = [
                Cotizacion.model_validate(item)
                for item in datos
            ]
            filtradas = [c for c in cotizaciones if c.desde == "USD" and c.hacia == "COP"]
            return sorted(filtradas, key=lambda c: c.fecha)
        except (OSError, ValueError, TypeError):
            return []

    def _leer_csv(self) -> list[Cotizacion]:
        if not self.ruta_csv.exists():
            return []
        try:
            with self.ruta_csv.open("r", encoding="utf-8", newline="") as archivo:
                lector = csv.DictReader(archivo)
                cotizaciones: list[Cotizacion] = []
                for fila in lector:
                    normalizada = {
                        k.strip().lower(): v for k, v in fila.items() if k is not None
                    }
                    if "valor" not in normalizada or "vigenciadesde" not in normalizada:
                        return []
                    cotizaciones.append(
                        Cotizacion(
                            desde="USD",
                            hacia="COP",
                            tasa=_parsear_decimal(normalizada["valor"]),
                            spread=SPREAD_POR_DEFECTO,
                            fecha=_parsear_fecha(str(normalizada["vigenciadesde"])),
                            fuente="simulado",
                        )
                    )
                return sorted(cotizaciones, key=lambda c: c.fecha)
        except (OSError, ValueError, KeyError, csv.Error):
            return []

    def _leer_fixtures(self) -> list[Cotizacion]:
        cotizaciones = [
            c for c in cargar_cotizaciones_ejemplo() if c.desde == "USD" and c.hacia == "COP"
        ]
        return sorted(cotizaciones, key=lambda c: c.fecha)


MercadoCSV = MercadoSocrata
