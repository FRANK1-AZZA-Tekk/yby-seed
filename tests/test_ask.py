"""Testes do fluxo mínimo ask."""

from click.testing import CliRunner

from src.core.graph import ask, build_ask_graph
from src.core.llm import LLMClient
from src.main import cli


runner = CliRunner()


class MockLLM(LLMClient):
    def generate(self, prompt: str) -> str:
        return f"resposta simulada: {prompt}"


class CapturingLLM(LLMClient):
    def __init__(self):
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "resposta com contexto"


def test_ask_graph_returns_answer():
    answer = ask("olá", llm=MockLLM())
    assert answer == "resposta simulada: olá"


def test_ask_graph_rejects_empty_question():
    graph = build_ask_graph(llm=MockLLM())
    try:
        graph.invoke({"question": "   ", "route": "", "answer": "", "citations": []})
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


def test_ask_with_cite_includes_retrieved_context(monkeypatch, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text(
        "# Guia\n\nO YBY usa arquitetura local-first.\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    llm = CapturingLLM()
    answer, citations = ask("arquitetura local-first", llm=llm, cite=True)

    assert answer == "resposta com contexto"
    assert len(llm.prompts) == 1
    assert "Documentos:" in llm.prompts[0]
    assert "arquitetura local-first" in llm.prompts[0]
    assert citations
    assert citations[0].startswith("docs/guide.md:")


def test_ask_without_cite_does_not_create_memory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ask("olá", llm=MockLLM())
    assert not (tmp_path / ".yby").exists()
