"""Testes unitários funcionais para o OllamaClient."""

import pytest
import requests
from unittest.mock import MagicMock, patch

from src.core.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaHTTPError,
    OllamaTimeoutError,
)


@pytest.fixture
def client():
    """OllamaClient com timeout curto para testes."""
    return OllamaClient(timeout=5)


def test_timeout_em_generate(client):
    """Timeout deve levantar OllamaTimeoutError."""
    with patch.object(
        client.session,
        "request",
        side_effect=requests.Timeout("timeout"),
    ):
        with pytest.raises(OllamaTimeoutError):
            client.generate("llama3.2:3b", "Olá")


def test_conexao_recusada_em_generate(client):
    """Falha de conexão deve levantar OllamaConnectionError."""
    with patch.object(
        client.session,
        "request",
        side_effect=requests.ConnectionError("recusado"),
    ):
        with pytest.raises(OllamaConnectionError):
            client.generate("llama3.2:3b", "Olá")


def test_erro_http_em_generate(client):
    """Erro HTTP deve levantar OllamaHTTPError."""
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = requests.HTTPError(
        "404", response=MagicMock(status_code=404)
    )

    with patch.object(
        client.session,
        "request",
        return_value=mock_response,
    ):
        with pytest.raises(OllamaHTTPError):
            client.generate("modelo-inexistente", "Olá")


def test_generate_retorna_resposta(client):
    """Resposta válida deve retornar o texto gerado."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "Olá!"}
    mock_response.raise_for_status.return_value = None

    with patch.object(
        client.session,
        "request",
        return_value=mock_response,
    ):
        resultado = client.generate("llama3.2:3b", "Olá")

    assert resultado == "Olá!"


def test_chat_retorna_conteudo(client):
    """Chat deve retornar o conteúdo da mensagem."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {"content": "Resposta do chat"}
    }
    mock_response.raise_for_status.return_value = None

    with patch.object(
        client.session,
        "request",
        return_value=mock_response,
    ):
        resultado = client.chat(
            "llama3.2:3b",
            [{"role": "user", "content": "Oi"}],
        )

    assert resultado == "Resposta do chat"


def test_is_healthy_false_em_erro(client):
    """is_healthy deve retornar False em falha de conexão."""
    with patch.object(
        client.session,
        "request",
        side_effect=requests.ConnectionError("offline"),
    ):
        assert client.is_healthy() is False
