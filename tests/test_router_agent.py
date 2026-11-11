"""Testes unitários funcionais para o RouterAgent."""

import json
from unittest.mock import MagicMock

import pytest
from src.agents.router_agent import RouterAgent


@pytest.fixture
def ollama_mock():
    """Mock do OllamaClient."""
    return MagicMock()


@pytest.fixture
def router(ollama_mock):
    """RouterAgent com Ollama simulado."""
    return RouterAgent(ollama=ollama_mock)


def test_classifica_backup_automation(router, ollama_mock):
    """Comando de backup deve rotear para planning."""
    ollama_mock.generate.return_value = json.dumps({
        "agent": "planning",
        "intent": "backup_automation",
        "confidence": 0.95,
        "requires_interview": True
    })

    resultado = router.classify("Crie um script de backup")

    assert resultado["agent"] == "planning"
    assert resultado["intent"] == "backup_automation"
    assert resultado["confidence"] == 0.95


def test_classifica_chat_question(router, ollama_mock):
    """Pergunta simples deve rotear para execution."""
    ollama_mock.generate.return_value = json.dumps({
        "agent": "execution",
        "intent": "chat_question",
        "confidence": 0.9,
        "requires_interview": False
    })

    resultado = router.classify("O que é backup?")

    assert resultado["agent"] == "execution"
    assert resultado["intent"] == "chat_question"


def test_fallback_json_invalido(router, ollama_mock):
    """Resposta sem JSON válido deve cair no fallback."""
    ollama_mock.generate.return_value = "resposta sem json"

    resultado = router.classify("comando estranho")

    assert resultado["agent"] == "planning"
    assert resultado["intent"] == "unknown"
    assert resultado["requires_interview"] is True


def test_json_aninhado(router, ollama_mock):
    """JSON com objetos aninhados não deve ser truncado no primeiro }."""
    ollama_mock.generate.return_value = (
        'texto {"agent": "planning", "intent": "api_integration", '
        '"confidence": 0.9, "meta": {"nested": true}, '
        '"requires_interview": true} fim'
    )
    resultado = router.classify("integre uma API")
    assert resultado["agent"] == "planning"
    assert resultado["intent"] == "api_integration"
    assert resultado["meta"]["nested"] is True


def test_resposta_vazia(router, ollama_mock):
    ollama_mock.generate.return_value = ""
    resultado = router.classify("oi")
    assert resultado["intent"] in {"unknown", "ollama_unavailable"}
    assert resultado.get("error")


def test_entrevista_por_voz_backup(router):
    """Backup deve exigir entrevista por voz."""
    assert router.should_use_voice_interview("backup_automation") is True


def test_entrevista_por_voz_chat(router):
    """Chat não deve exigir entrevista por voz."""
    assert router.should_use_voice_interview("chat_question") is False
