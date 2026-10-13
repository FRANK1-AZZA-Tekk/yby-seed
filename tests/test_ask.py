"""Testes do fluxo mínimo ask."""

from click.testing import CliRunner

from src.core.graph import ask, build_ask_graph
from src.core.llm import LLMClient
from src.main import cli


runner = CliRunner()


class MockLLM(LLMClient):
    def generate(self, prompt: str) -> str:
        return f"resposta simulada: {prompt}"


def test_ask_graph_returns_answer():
    answer = ask("olá", llm=MockLLM())
    assert answer == "resposta simulada: olá"


def test_ask_graph_rejects_empty_question():
    graph = build_ask_graph(llm=MockLLM())
    try:
        graph.invoke({"question": "   ", "route": "", "answer": ""})
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_ask_cli_uses_mock_provider():
    result = runner.invoke(cli, ["ask", "olá"])
    assert result.exit_code == 0
    assert "[mock] Resposta para: olá" in result.output


def test_ask_cli_rejects_empty_question():
    result = runner.invoke(cli, ["ask", "   "])
    assert result.exit_code == 1
