from unittest.mock import patch

from click.testing import CliRunner

from src.main import cli


def test_stop_does_not_construct_ollama_client():
    with patch("src.main.OllamaClient") as client_class:
        result = CliRunner().invoke(cli, ["ask", "parar"])

    assert result.exit_code == 0
    assert "Solicitação encerrada." in result.output
    client_class.assert_not_called()


def test_unimplemented_command_returns_exit_5():
    with patch("src.main.OllamaClient") as client_class:
        result = CliRunner().invoke(cli, ["ask", "modo offline"])

    assert result.exit_code == 5
    assert "ainda não está implementada" in result.output
    client_class.assert_not_called()


def test_normal_prompt_reaches_generation_path():
    with patch("src.main.OllamaClient") as client_class:
        instance = client_class.return_value
        instance.is_healthy.return_value = True
        instance.list_models.return_value = ["qwen3:4b"]
        instance.generate.return_value = "ok"

        result = CliRunner().invoke(cli, ["ask", "como faço para parar de fumar"])

    assert result.exit_code == 0
    instance.generate.assert_called_once()
