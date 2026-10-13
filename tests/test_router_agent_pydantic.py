"""Testes para validação Pydantic no RouterAgent."""

import json
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from src.agents.router_agent import RouterAgent, RouterResult
from src.core.ollama_client import OllamaClient


@pytest.fixture
def router():
    """RouterAgent com OllamaClient mockado."""
    mock_ollama = MagicMock(spec=OllamaClient)
    return RouterAgent(mock_ollama)


def test_router_result_schema_valido():
    """RouterResult deve aceitar dados válidos."""
    result = RouterResult(
        agent="planning",
        intent="backup_automation",
        confidence=0.9,
        requires_interview=True,
    )

    assert result.agent == "planning"
    assert result.intent == "backup_automation"
    assert result.confidence == 0.9
    assert result.requires_interview is True


def test_router_result_agent_invalido():
    """Agent inválido deve levantar ValidationError."""
    with pytest.raises(ValidationError):
        RouterResult(
            agent="desconhecido",
            intent="x",
            confidence=0.5,
        )


def test_router_result_confidence_fora_do_range():
    """Confidence fora de 0.0-1.0 deve levantar ValidationError."""
    with pytest.raises(ValidationError):
        RouterResult(
            agent="planning",
            intent="x",
            confidence=1.5,
        )


def test_classify_retorna_router_result(router):
    """classify deve retornar RouterResult validado."""
    router.ollama.generate.return_value = json.dumps({
        "agent": "planning",
        "intent": "backup_automation",
        "confidence": 0.9,
        "requires_interview": True,
    })

    result = router.classify("Crie um script de backup")

    assert isinstance(result, RouterResult)
    assert result.agent == "planning"
    assert result.intent == "backup_automation"
    assert result.confidence == 0.9
    assert result.requires_interview is True


def test_classify_fallback_em_json_invalido(router):
    """JSON inválido deve cair no fallback."""
    router.ollama.generate.return_value = "não é json"

    result = router.classify("comando qualquer")

    assert isinstance(result, RouterResult)
    assert result.agent == "planning"
    assert result.intent == "unknown"
    assert result.confidence == 0.5
    assert result.requires_interview is True


def test_classify_fallback_em_validacao_falha(router):
    """Validação Pydantic falha deve cair no fallback."""
    router.ollama.generate.return_value = json.dumps({
        "agent": "desconhecido",
        "intent": "x",
        "confidence": 0.5,
    })

    result = router.classify("comando qualquer")

    assert isinstance(result, RouterResult)
    assert result.agent == "planning"
    assert result.intent == "unknown"
    assert result.confidence == 0.5
    assert result.requires_interview is True


def test_should_use_voice_interview(router):
    """Intenções de entrevista por voz devem retornar True."""
    assert router.should_use_voice_interview("backup_automation") is True
    assert router.should_use_voice_interview("chat_question") is False
