from unittest.mock import patch

from click.testing import CliRunner

import src.main as main
from src.core.router import RunPolicy, route_request


def test_default_policy_routes_to_local_ollama():
    decision = route_request(RunPolicy())

    assert decision.route == "local_ollama"
    assert decision.policy.offline is False
    assert decision.policy.private is False


def test_offline_and_private_are_preserved():
    decision = route_request(RunPolicy(offline=True, private=True))

    assert decision.route == "local_ollama"
    assert decision.policy.offline is True
    assert decision.policy.private is True


def test_no_cloud_route_exists():
    for policy in (
        RunPolicy(),
        RunPolicy(offline=True),
        RunPolicy(private=True),
        RunPolicy(offline=True, private=True),
    ):
        decision = route_request(policy)
        assert decision.route == "local_ollama"


def test_ask_accepts_offline_and_private_flags():
    with patch("src.main.OllamaClient") as client_class:
        client = client_class.return_value
        client.is_healthy.return_value = True
        client.list_models.return_value = [main.DEFAULT_MODEL]
        client.generate.return_value = "ok"

        result = CliRunner().invoke(
            main.cli,
            ["ask", "--offline", "--private", "Olá"],
        )

    assert result.exit_code == 0
    assert result.output.strip() == "ok"


def test_ask_offline_still_uses_local_ollama_only():
    with patch("src.main.OllamaClient") as client_class:
        client = client_class.return_value
        client.is_healthy.return_value = True
        client.list_models.return_value = [main.DEFAULT_MODEL]
        client.generate.return_value = "resposta"

        result = CliRunner().invoke(
            main.cli,
            ["ask", "--offline", "Olá"],
        )

    assert result.exit_code == 0
    client_class.assert_called_once()
