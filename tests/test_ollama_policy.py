from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

import src.main as main
from src.core.ollama_client import (
    OllamaClient,
    OllamaPolicyError,
)


OPERATIONS = (
    "generate",
    "generate_stream",
    "list_models",
    "is_healthy",
    "chat",
    "chat_stream",
    "pull",
)


def invoke_operation(client, operation):
    operations = {
        "generate": lambda: client.generate(
            model="qwen3:4b",
            prompt="Teste",
        ),
        "generate_stream": lambda: client.generate(
            model="qwen3:4b",
            prompt="Teste",
            stream=True,
        ),
        "list_models": client.list_models,
        "is_healthy": client.is_healthy,
        "chat": lambda: client.chat(
            model="qwen3:4b",
            messages=[{"role": "user", "content": "Teste"}],
        ),
        "chat_stream": lambda: client.chat(
            model="qwen3:4b",
            messages=[{"role": "user", "content": "Teste"}],
            stream=True,
        ),
        "pull": lambda: client.pull("qwen3:4b"),
    }
    return operations[operation]()


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("localhost", "http://127.0.0.1:11434"),
        ("127.0.0.1", "http://127.0.0.1:11434"),
        ("::1", "http://[::1]:11434"),
    ],
)
def test_loopback_hosts_are_canonicalized(host, expected):
    client = OllamaClient(host=host)
    try:
        assert client.base_url == expected
        assert client.session.trust_env is False
    finally:
        client.session.close()


@pytest.mark.parametrize(
    "host",
    [
        "192.168.1.10",
        "0.0.0.0",
        "example.com",
        "localhost.example.com",
        "127.0.0.1@example.com",
        "http://127.0.0.1",
        "[::1]",
        "",
        " localhost",
    ],
)
def test_forbidden_host_is_rejected_before_session_creation(host):
    with patch(
        "src.core.ollama_client.requests.Session"
    ) as session_class:
        with pytest.raises(OllamaPolicyError):
            OllamaClient(host=host)

    session_class.assert_not_called()


@pytest.mark.parametrize("port", [0, -1, 65536, True, "11434"])
def test_invalid_port_is_rejected_before_session_creation(port):
    with patch(
        "src.core.ollama_client.requests.Session"
    ) as session_class:
        with pytest.raises(OllamaPolicyError):
            OllamaClient(port=port)

    session_class.assert_not_called()


@pytest.mark.parametrize("operation", OPERATIONS)
def test_all_operations_disable_redirects(monkeypatch, operation):
    client = OllamaClient()
    response = Mock(status_code=200)
    response.json.return_value = {
        "response": "ok",
        "models": [],
        "message": {"content": "ok"},
    }
    response.iter_lines.return_value = [b'{"response":"ok"}']
    request = Mock(return_value=response)
    monkeypatch.setattr(client.session, "request", request)

    try:
        result = invoke_operation(client, operation)
        if operation in ("generate_stream", "chat_stream"):
            list(result)

        request.assert_called_once()
        assert request.call_args.kwargs["allow_redirects"] is False
        assert request.call_args.args[1].startswith(
            "http://127.0.0.1:11434/"
        )

        expected_timeout = (
            5.0 if operation == "is_healthy" else client.timeout
        )
        assert request.call_args.kwargs["timeout"] == expected_timeout
    finally:
        client.session.close()


@pytest.mark.parametrize("operation", OPERATIONS)
@pytest.mark.parametrize("status", [300, 301, 302, 303, 304, 307, 308, 399])
def test_redirect_is_closed_and_never_swallowed(
    monkeypatch, operation, status
):
    client = OllamaClient()
    response = Mock(status_code=status)
    response.headers = {"Location": "https://example.com/SEGREDO_TESTE"}
    request = Mock(return_value=response)
    monkeypatch.setattr(client.session, "request", request)

    try:
        with pytest.raises(OllamaPolicyError) as caught:
            invoke_operation(client, operation)

        request.assert_called_once()
        response.close.assert_called_once()
        response.json.assert_not_called()
        assert "SEGREDO_TESTE" not in str(caught.value)
    finally:
        client.session.close()


@pytest.mark.parametrize(
    ("args", "expected_exit"),
    [
        (["ask", "Olá"], 6),
        (["health"], 1),
    ],
)
def test_cli_rejects_remote_host_before_http(
    monkeypatch, args, expected_exit
):
    monkeypatch.setattr(main, "OLLAMA_HOST", "192.168.1.10")
    monkeypatch.setattr(main, "OLLAMA_PORT", "11434")

    with patch(
        "src.core.ollama_client.requests.Session"
    ) as session_class:
        result = CliRunner().invoke(main.cli, args)

    assert result.exit_code == expected_exit
    assert "política local" in result.output
    session_class.assert_not_called()


@pytest.mark.parametrize("port", ["abc", "", "0", "65536"])
def test_cli_invalid_port_is_controlled(monkeypatch, port):
    monkeypatch.setattr(main, "OLLAMA_HOST", "localhost")
    monkeypatch.setattr(main, "OLLAMA_PORT", port)

    with patch(
        "src.core.ollama_client.requests.Session"
    ) as session_class:
        result = CliRunner().invoke(main.cli, ["ask", "Olá"])

    assert result.exit_code == 6
    assert "Porta" in result.output
    session_class.assert_not_called()


def test_stop_works_with_invalid_endpoint_configuration(monkeypatch):
    monkeypatch.setattr(main, "OLLAMA_HOST", "example.com")
    monkeypatch.setattr(main, "OLLAMA_PORT", "invalida")

    with patch("src.main.OllamaClient") as client_class:
        result = CliRunner().invoke(main.cli, ["ask", "parar"])

    assert result.exit_code == 0
    client_class.assert_not_called()


@pytest.mark.parametrize(
    "stage",
    ["is_healthy", "list_models", "generate"],
)
def test_ask_policy_error_is_exit_six(stage):
    with patch("src.main.OllamaClient") as client_class:
        client = client_class.return_value
        client.is_healthy.return_value = True
        client.list_models.return_value = [main.DEFAULT_MODEL]
        client.generate.return_value = "ok"
        getattr(client, stage).side_effect = OllamaPolicyError(
            "Redirecionamento bloqueado pela política local."
        )

        result = CliRunner().invoke(main.cli, ["ask", "Olá"])

    assert result.exit_code == 6
    assert "bloqueado" in result.output
