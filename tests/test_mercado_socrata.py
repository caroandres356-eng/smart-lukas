"""Tests del pipeline TRM vía API Socrata (`banco/mercado.py`) sin internet real."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from banco.mercado import MercadoCSV, MercadoSocrata
from core.modelos import Cotizacion
from core.puertos import MercadoPort
from fakes.fakes import cargar_cotizaciones_ejemplo


def _respuesta_socrata_ejemplo() -> list[dict[str, str]]:
    """Simula respuesta SODA2 ordenada DESC por vigenciadesde (como devuelve datos.gov.co)."""
    return [
        {
            "valor": "4125.50",
            "unidad": "COP",
            "vigenciadesde": "2026-11-23T00:00:00.000",
            "vigenciahasta": "2026-11-23T00:00:00.000",
        },
        {
            "valor": "4110.25",
            "unidad": "COP",
            "vigenciadesde": "2026-11-20T00:00:00.000",
            "vigenciahasta": "2026-11-22T00:00:00.000",
        },
        {
            "valor": "4098.00",
            "unidad": "COP",
            "vigenciadesde": "2026-11-19T00:00:00.000",
        },
    ]


def test_cumple_mercado_port_y_alias(tmp_path: Path) -> None:
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=[]))
    mercado = MercadoSocrata(
        tmp_path / "inexistente.csv",
        ruta_cache=tmp_path / "cache.json",
        transport=transport,
    )
    assert MercadoCSV is MercadoSocrata
    assert isinstance(mercado, MercadoPort)


def test_envia_cabecera_x_app_token_por_parametro_y_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cabeceras_vistas: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        cabeceras_vistas.append(request.headers.get("X-App-Token"))
        return httpx.Response(200, json=_respuesta_socrata_ejemplo())

    mercado_param = MercadoSocrata(
        tmp_path / "trm.csv",
        ruta_cache=tmp_path / "cache_param.json",
        app_token="token-directo-123",
        transport=httpx.MockTransport(handler),
    )
    mercado_param.extraer_socrata(dias=3)

    monkeypatch.setenv("SOCRATA_APP_TOKEN", "token-env-456")
    mercado_env = MercadoSocrata(
        tmp_path / "trm.csv",
        ruta_cache=tmp_path / "cache_env.json",
        transport=httpx.MockTransport(handler),
    )
    mercado_env.extraer_socrata(dias=3)

    assert cabeceras_vistas == ["token-directo-123", "token-env-456"]


def test_parsea_socrata_ordena_respeta_dias_y_escribe_cache(tmp_path: Path) -> None:
    peticiones: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        peticiones.append(request)
        return httpx.Response(200, json=_respuesta_socrata_ejemplo())

    ruta_cache = tmp_path / "sub" / "trm_cache.json"
    mercado = MercadoSocrata(
        tmp_path / "inexistente.csv",
        ruta_cache=ruta_cache,
        transport=httpx.MockTransport(handler),
    )

    resultado = mercado.historico("USD", "COP", dias=2)

    assert len(peticiones) == 1
    assert peticiones[0].url.params["$order"] == "vigenciadesde DESC"
    assert peticiones[0].url.params["$limit"] == "60"
    assert len(resultado) == 2

    # Ordenadas de más antigua a más reciente (últimos 2 días del lote de 3)
    assert [c.fecha for c in resultado] == [date(2026, 11, 20), date(2026, 11, 23)]
    assert [c.tasa for c in resultado] == [Decimal("4110.25"), Decimal("4125.50")]
    for c in resultado:
        assert isinstance(c, Cotizacion)
        assert isinstance(c.tasa, Decimal)
        assert c.spread == Decimal("0.01")
        assert c.fuente == "simulado"
        assert c.desde == "USD"
        assert c.hacia == "COP"

    # Verifica escritura de caché JSON completa (3 registros ordenados)
    assert ruta_cache.exists()
    cache_json = json.loads(ruta_cache.read_text(encoding="utf-8"))
    assert len(cache_json) == 3
    assert [item["fecha"] for item in cache_json] == [
        "2026-11-19",
        "2026-11-20",
        "2026-11-23",
    ]
    assert cache_json[0]["tasa"] == "4098.00"


def test_extraer_socrata_con_hasta_envia_where(tmp_path: Path) -> None:
    params_vistos: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        params_vistos.update(dict(request.url.params))
        return httpx.Response(200, json=_respuesta_socrata_ejemplo())

    mercado = MercadoSocrata(
        tmp_path / "trm.csv",
        ruta_cache=tmp_path / "cache.json",
        transport=httpx.MockTransport(handler),
    )
    mercado.extraer_socrata(dias=40, hasta=date(2026, 11, 20))

    assert params_vistos["$limit"] == "80"
    assert params_vistos["$where"] == "vigenciadesde <= '2026-11-20T23:59:59'"


@pytest.mark.parametrize("modo_fallo", ["http_500", "connect_error"])
def test_fallback_a_cache_json_cuando_socrata_falla(
    tmp_path: Path, modo_fallo: str
) -> None:
    ruta_cache = tmp_path / "trm_cache.json"
    cache_data = [
        {
            "desde": "USD",
            "hacia": "COP",
            "tasa": "4050.10",
            "spread": "0.01",
            "fecha": "2026-11-10",
            "fuente": "simulado",
        },
        {
            "desde": "USD",
            "hacia": "COP",
            "tasa": "4060.20",
            "spread": "0.01",
            "fecha": "2026-11-11",
            "fuente": "simulado",
        },
    ]
    ruta_cache.write_text(json.dumps(cache_data), encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if modo_fallo == "http_500":
            return httpx.Response(500, json={"error": "server error"})
        raise httpx.ConnectError("sin red", request=request)

    mercado = MercadoSocrata(
        tmp_path / "inexistente.csv",
        ruta_cache=ruta_cache,
        transport=httpx.MockTransport(handler),
    )
    cotizaciones = mercado.historico("USD", "COP", dias=5)

    assert len(cotizaciones) == 2
    assert [c.fecha for c in cotizaciones] == [date(2026, 11, 10), date(2026, 11, 11)]
    assert [c.tasa for c in cotizaciones] == [Decimal("4050.10"), Decimal("4060.20")]


def test_fallback_a_csv_cuando_fallan_socrata_y_cache(tmp_path: Path) -> None:
    ruta_csv = tmp_path / "trm.csv"
    ruta_csv.write_text(
        "VALOR,VIGENCIADESDE,VIGENCIAHASTA\n"
        "4015.75,2026-11-05T00:00:00.000,2026-11-05T00:00:00.000\n"
        "4002.00,2026-11-04T00:00:00.000,2026-11-04T00:00:00.000\n",
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red", request=request)

    mercado = MercadoSocrata(
        ruta_csv,
        ruta_cache=tmp_path / "cache_inexistente.json",
        transport=httpx.MockTransport(handler),
    )
    cotizaciones = mercado.historico("USD", "COP", dias=10)

    assert [c.fecha for c in cotizaciones] == [date(2026, 11, 4), date(2026, 11, 5)]
    assert [c.tasa for c in cotizaciones] == [Decimal("4002.00"), Decimal("4015.75")]


def test_fallback_a_fixtures_cuando_fallan_socrata_cache_y_csv(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    mercado = MercadoSocrata(
        tmp_path / "no_existe.csv",
        ruta_cache=tmp_path / "no_existe_cache.json",
        transport=httpx.MockTransport(handler),
    )

    cotizaciones = mercado.historico("USD", "COP", dias=7)
    esperadas = cargar_cotizaciones_ejemplo()[-7:]

    assert len(cotizaciones) == 7
    assert cotizaciones == esperadas


def test_cotizacion_para_fecha_resuelve_fines_de_semana(tmp_path: Path) -> None:
    # 2026-11-20 es viernes, 2026-11-21 es sábado, 2026-11-22 es domingo, 2026-11-23 es lunes
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json=_respuesta_socrata_ejemplo())
    )
    mercado = MercadoSocrata(
        tmp_path / "trm.csv",
        ruta_cache=tmp_path / "cache.json",
        transport=transport,
    )

    sabado = mercado.cotizacion_para_fecha(date(2026, 11, 21))
    domingo = mercado.cotizacion_para_fecha(date(2026, 11, 22))
    lunes = mercado.cotizacion_para_fecha(date(2026, 11, 23))
    anterior = mercado.cotizacion_para_fecha(date(2026, 11, 10))

    assert sabado.tasa == Decimal("4110.25")
    assert sabado.fecha == date(2026, 11, 21)
    assert domingo.tasa == Decimal("4110.25")
    assert domingo.fecha == date(2026, 11, 22)
    assert lunes.tasa == Decimal("4125.50")
    assert lunes.fecha == date(2026, 11, 23)
    assert anterior.tasa == Decimal("4098.00")
    assert anterior.fecha == date(2026, 11, 10)


def test_validacion_moneda_y_dias_no_positivos(tmp_path: Path) -> None:
    mercado = MercadoSocrata(
        tmp_path / "trm.csv",
        ruta_cache=tmp_path / "cache.json",
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=[])),
    )
    with pytest.raises(ValueError):
        mercado.historico("USDT", "COP", 5)

    assert mercado.historico("USD", "COP", 0) == []
    assert mercado.historico("USD", "COP", -3) == []
