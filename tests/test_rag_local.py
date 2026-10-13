"""Testes do RAG local mínimo com citações."""

from pathlib import Path

from click.testing import CliRunner

from src.core.graph import ask
from src.core.llm import LLMClient
from src.core.rag import build_index, search
from src.main import cli


runner = CliRunner()


class MockLLM(LLMClient):
    def generate(self, prompt: str) -> str:
        return "resposta com contexto simulado"


def test_build_index_reads_markdown(tmp_path: Path):
    doc = tmp_path / "doc.md"
    doc.write_text("# Titulo\n\nO YBY usa arquitetura local-first.\n", encoding="utf-8")
    chunks = build_index([doc])
    assert len(chunks) == 2
    assert chunks[1].source == str(doc)


def test_search_returns_relevant_chunk(tmp_path: Path):
    doc = tmp_path / "doc.md"
    doc.write_text("# Titulo\n\nO YBY usa arquitetura local-first.\n", encoding="utf-8")
    chunks = build_index([doc])
    results = search("arquitetura local-first", chunks)
    assert results
    assert "arquitetura local-first" in results[0].text


def test_ask_with_citations_returns_sources(tmp_path: Path):
    doc = tmp_path / "doc.md"
    doc.write_text("# Titulo\n\nO YBY usa arquitetura local-first.\n", encoding="utf-8")
    answer, citations = ask("arquitetura local-first", llm=MockLLM(), cite=True)
    assert answer
    assert citations


def test_ask_cli_with_cite(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "guide.md").write_text("# Guia\n\nO YBY usa arquitetura local-first.\n", encoding="utf-8")
    result = runner.invoke(cli, ["ask", "--cite", "arquitetura local-first"])
    assert result.exit_code == 0
    assert "Fontes:" in result.output
    assert "docs/guide.md:" in result.output
