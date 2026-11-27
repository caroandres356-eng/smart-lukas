"""Tests de contrato para los esqueletos Belo API/MCP y el cliente DeepSeek."""

from __future__ import annotations

import json

import httpx
import pytest
from pydantic import ValidationError

from agente import (
    AgenteExplicadorPort,
    AgenteLLMConfig,
    DeepSeekCliente,
    validar_montos_en_texto,
)
from agente.deepseek_cliente import AgenteExplicadorSeguro
from banco.fabrica import MODOS
from banco.belo_api import BeloApiBanco
from banco.belo_mcp import BeloMcpBanco
from core.puertos import BancoPort
from scripts.verificar_conectores import diagnosticar_entorno


# --------------------------------------------------------------------------- Belo API / MCP


def test_belo_api_esta_configurado_y_cumple_puerto(monkeypatch):
    monkeypatch.delenv("BELO_API_URL", raising=False)
    monkeypatch.delenv("BELO_API_KEY", raising=False)

    sin_creds = BeloApiBanco()
    assert isinstance(sin_creds, BancoPort)
    assert sin_creds.esta_configurado() is False

    monkeypatch.setenv("BELO_API_URL", "https://api.belo.app")
    assert BeloApiBanco().esta_configurado() is False

    monkeypatch.setenv("BELO_API_KEY", "secret-belo")
    con_env = BeloApiBanco()
    assert con_env.esta_configurado() is True
    assert con_env.url == "https://api.belo.app"
    assert con_env.api_key == "secret-belo"

    assert BeloApiBanco(url="https://sandbox.belo.app", api_key="k").esta_configurado() is True


def test_belo_mcp_esta_configurado_y_cumple_puerto(monkeypatch):
    monkeypatch.delenv("BELO_MCP_URL", raising=False)
    sin_url = BeloMcpBanco()
    assert isinstance(sin_url, BancoPort)
    assert sin_url.esta_configurado() is False

    monkeypatch.setenv("BELO_MCP_URL", "   ")
    assert BeloMcpBanco().esta_configurado() is False

    monkeypatch.setenv("BELO_MCP_URL", "https://mcp.belo.app/sse")
    con_env = BeloMcpBanco()
    assert con_env.esta_configurado() is True
    assert con_env.url == "https://mcp.belo.app/sse"


@pytest.mark.parametrize("modo", MODOS)
def test_diagnostico_reconoce_modos_de_fabrica(monkeypatch, modo):
    monkeypatch.setenv("BANCO_MODO", modo)
    assert diagnosticar_entorno()["BANCO_MODO"]["configurado"] is True


def test_diagnostico_usa_fakes_por_defecto_y_rechaza_modo_invalido(monkeypatch):
    monkeypatch.delenv("BANCO_MODO", raising=False)
    assert diagnosticar_entorno()["BANCO_MODO"]["configurado"] is True

    monkeypatch.setenv("BANCO_MODO", "belo")
    assert diagnosticar_entorno()["BANCO_MODO"]["configurado"] is False


# --------------------------------------------------------------------------- DeepSeek


def test_deepseek_config_defaults_y_validacion(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_BASE_URL", raising=False)
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)

    cfg = AgenteLLMConfig.desde_env()
    assert cfg.api_key == ""
    assert cfg.base_url == "https://api.deepseek.com"
    assert cfg.model == "deepseek-chat"

    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-env")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-reasoner")
    cfg_env = AgenteLLMConfig.desde_env()
    assert cfg_env.api_key == "sk-env"
    assert cfg_env.base_url == "https://api.deepseek.com"
    assert cfg_env.model == "deepseek-reasoner"

    with pytest.raises(ValidationError):
        AgenteLLMConfig(api_key="x", campo_invalido=123)


def test_deepseek_sin_api_key_no_configurado_y_lanza_not_implemented(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    cliente = DeepSeekCliente()
    assert isinstance(cliente, AgenteExplicadorPort)
    assert cliente.esta_configurado() is False

    with pytest.raises(NotImplementedError, match="pendiente DEEPSEEK_API_KEY en .env"):
        cliente.completar("Eres asistente.", "Explica esta ruta.")


def test_deepseek_completar_con_mock_transport():
    captura: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captura["method"] = request.method
        captura["url"] = str(request.url)
        captura["auth"] = request.headers.get("Authorization")
        captura["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Conviene convertir 450 USD."}}],
            },
        )

    transport = httpx.MockTransport(handler)
    cliente = DeepSeekCliente(
        api_key="sk-test-123",
        base_url="https://api.deepseek.com/",
        model="deepseek-chat",
        transport=transport,
    )
    assert cliente.esta_configurado() is True

    texto = cliente.completar("Solo redacta.", "Resume 450 USD.")
    assert texto == "Conviene convertir 450 USD."
    assert captura["method"] == "POST"
    assert captura["url"] == "https://api.deepseek.com/v1/chat/completions"
    assert captura["auth"] == "Bearer sk-test-123"
    assert captura["body"] == {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Solo redacta."},
            {"role": "user", "content": "Resume 450 USD."},
        ],
        "temperature": 0,
    }


def test_validar_montos_en_texto():
    permitidos = {"450", "1800000", "15"}
    assert validar_montos_en_texto("Conviene convertir $450.00 USD para cubrir $1,800,000 COP (15%).", permitidos) is True
    assert validar_montos_en_texto("Mandato AP2 aprobado sin cifras.", permitidos) is True
    assert validar_montos_en_texto("Conviene convertir 999 USD hoy.", permitidos) is False
    assert validar_montos_en_texto("Te sobran 450.01 USD.", permitidos) is False


# --------------------------------------------------------------------------- AgenteExplicadorSeguro


_RESUMEN = {"monto_usd": "100.00", "accion": "conversion"}
_PLANTILLA = "Resumen: se convirtieron 100.00 USD."
_PERMITIDOS = {"100.00", "100"}


def test_seguro_sin_cliente_cae_a_plantilla() -> None:
    """Sin cliente configurado devuelve la plantilla con origen 'plantilla'."""
    seguro = AgenteExplicadorSeguro(cliente=None)
    texto, origen = seguro.explicar_seguro(_RESUMEN, _PLANTILLA, _PERMITIDOS)
    assert origen == "plantilla"
    assert texto == _PLANTILLA


def test_seguro_sin_api_key_cae_a_plantilla(monkeypatch) -> None:
    """Con DeepSeekCliente sin API key (no configurado) cae a 'plantilla'."""
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    cliente = DeepSeekCliente()
    assert cliente.esta_configurado() is False

    seguro = AgenteExplicadorSeguro(cliente=cliente)
    texto, origen = seguro.explicar_seguro(_RESUMEN, _PLANTILLA, _PERMITIDOS)
    assert origen == "plantilla"
    assert texto == _PLANTILLA


def test_seguro_con_mock_transport_retorna_deepseek() -> None:
    """Con API key + MockTransport válido y texto sin montos inventados → origen 'deepseek'."""
    respuesta_llm = "Se convirtieron 100.00 USD correctamente."

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": respuesta_llm}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    cliente = DeepSeekCliente(api_key="sk-test-seguro", transport=transport)
    assert cliente.esta_configurado() is True

    seguro = AgenteExplicadorSeguro(cliente=cliente)
    texto, origen = seguro.explicar_seguro(_RESUMEN, _PLANTILLA, _PERMITIDOS)
    assert origen == "deepseek"
    assert texto == respuesta_llm


def test_seguro_llm_alucina_monto_cae_a_plantilla() -> None:
    """LLM que inventa un monto no permitido hace que caiga a 'plantilla'."""
    respuesta_alucinada = "Se convirtieron 999.99 USD (alucinación)."

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": respuesta_alucinada}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    cliente = DeepSeekCliente(api_key="sk-test-alucinacion", transport=transport)

    seguro = AgenteExplicadorSeguro(cliente=cliente)
    texto, origen = seguro.explicar_seguro(_RESUMEN, _PLANTILLA, _PERMITIDOS)
    assert origen == "plantilla"
    assert texto == _PLANTILLA


def test_seguro_error_de_red_cae_a_plantilla() -> None:
    """Un error de red (excepción) hace que caiga a 'plantilla'."""

    def handler_falla(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Red caída")

    transport = httpx.MockTransport(handler_falla)
    cliente = DeepSeekCliente(api_key="sk-test-red", transport=transport)

    seguro = AgenteExplicadorSeguro(cliente=cliente)
    texto, origen = seguro.explicar_seguro(_RESUMEN, _PLANTILLA, _PERMITIDOS)
    assert origen == "plantilla"
    assert texto == _PLANTILLA
