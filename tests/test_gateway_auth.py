"""Token do gateway e host local."""

from src.gateway.auth import check_token
from src.gateway.config import load_settings


def test_host_padrao_e_loopback() -> None:
    settings = load_settings({})
    assert settings.FASTAPI_HOST == "127.0.0.1"
    assert settings.OLLAMA_MODEL_LLM == "qwen2.5-coder:3b"
    assert settings.GATEWAY_TOKEN == ""


def test_host_e_token_configuraveis() -> None:
    settings = load_settings({"FASTAPI_HOST": "0.0.0.0", "GATEWAY_TOKEN": "segredo"})
    assert settings.FASTAPI_HOST == "0.0.0.0"
    assert settings.GATEWAY_TOKEN == "segredo"


def test_sem_token_as_rotas_fecham() -> None:
    ok, status, detail = check_token({}, "")
    assert ok is False
    assert status == 503
    assert "GATEWAY_TOKEN" in detail


def test_bearer_aceito_e_token_errado_recusado() -> None:
    ok, status, _detail = check_token({"Authorization": "Bearer segredo"}, "segredo")
    assert ok is True
    assert status == 200

    ok, status, detail = check_token({"X-API-Token": "outro"}, "segredo")
    assert ok is False
    assert status == 401
    assert detail == "token inválido"
