"""Testes da memória persistente local."""

from pathlib import Path

from click.testing import CliRunner

from src.core.graph import ask
from src.core.llm import LLMClient
from src.core.memory import MemoryStore
from src.main import cli


runner = CliRunner()


class MockLLM(LLMClient):
    def generate(self, prompt: str) -> str:
        return "resposta simulada"


def test_memory_store_persists_entries(tmp_path: Path):
    memory = MemoryStore(tmp_path / "memory.jsonl")
    memory.add("qual é a arquitetura?", "local-first")
    memory.add("outro assunto", "resposta")
    assert len(memory.list()) == 2


def test_memory_search_returns_relevant_entry(tmp_path: Path):
    memory = MemoryStore(tmp_path / "memory.jsonl")
    memory.add("qual é a arquitetura?", "local-first")
    memory.add("outro assunto", "resposta")
    results = memory.search("arquitetura")
    assert len(results) == 1
    assert results[0].answer == "local-first"


def test_ask_with_remember_persists_interaction(tmp_path: Path):
    memory = MemoryStore(tmp_path / "memory.jsonl")
    ask("qual é a arquitetura?", llm=MockLLM(), remember=True, memory=memory)
    assert len(memory.list()) == 1


def test_ask_cli_with_remember_and_memory_dir(tmp_path: Path):
    result = runner.invoke(
        cli,
        ["ask", "--remember", "--memory-dir", str(tmp_path), "qual é a arquitetura?"],
    )
    assert result.exit_code == 0
    memory = MemoryStore(tmp_path / "memory.jsonl")
    assert len(memory.list()) == 1
