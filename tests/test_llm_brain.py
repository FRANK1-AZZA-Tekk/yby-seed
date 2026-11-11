"""Testes do cérebro LiteLLM (Passo 2)."""

from types import SimpleNamespace
from unittest.mock import patch

from modules.llm_brain import LLMConfig, ask_llm, load_llm_config


def test_load_config_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("OPENROUTER_MODEL", "openrouter/meta-llama/llama-3.2-3b-instruct:free")
    cfg = load_llm_config()
    assert cfg.provider == "openrouter"
    assert cfg.api_key == "sk-test"
    assert cfg.model.startswith("openrouter/")


def test_load_config_fallback_ollama(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("OLLAMA_DEFAULT_MODEL", "llama3.2:3b")
    cfg = load_llm_config()
    assert cfg.provider == "ollama"
    assert cfg.model == "ollama/llama3.2:3b"
    assert cfg.api_base == "http://127.0.0.1:11434"


def test_ask_llm_returns_content():
    fake = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="  ok  "))]
    )
    cfg = LLMConfig(provider="ollama", model="ollama/llama3.2:3b", api_base="http://x")
    with patch("modules.llm_brain.completion", return_value=fake) as mocked:
        text = ask_llm("Status do sistema", cfg)
        assert text == "ok"
        mocked.assert_called_once()
        kwargs = mocked.call_args.kwargs
        assert kwargs["model"] == "ollama/llama3.2:3b"
        assert kwargs["api_base"] == "http://x"
