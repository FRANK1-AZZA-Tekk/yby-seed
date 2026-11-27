"""Testes do classificador determinístico por regras."""

from __future__ import annotations

import pytest

from src.router.classifier import classify, classify_result
from src.router.errors import RoutingError, SafetyViolationError
from src.router.policy import (
    MODEL_AUTOMATION,
    MODEL_CODING,
    MODEL_FALLBACK,
    MODEL_GENERAL,
    MODEL_KNOWLEDGE,
)
from src.router.schemas import Request


def test_classifies_four_intents() -> None:
    general = classify("oi, tudo bem?")
    coding = classify("corrija o bug nesta função python")
    knowledge = classify("o que é o YBY SEED e como funciona?")
    automation = classify("automatizar o backup com um script agendado")

    assert general.intent == "general"
    assert coding.intent == "coding"
    assert knowledge.intent == "knowledge"
    assert automation.intent == "automation"

    assert general.selected_model == MODEL_GENERAL
    assert coding.selected_model == MODEL_CODING
    assert knowledge.selected_model == MODEL_KNOWLEDGE
    assert automation.selected_model == MODEL_AUTOMATION


def test_fallback_per_profile() -> None:
    for text, intent in (
        ("olá", "general"),
        ("implemente um teste pytest", "coding"),
        ("explique a documentação do vault", "knowledge"),
        ("executar o comando de limpeza", "automation"),
    ):
        decision = classify(text)
        assert decision.intent == intent
        assert decision.fallback_model == MODEL_FALLBACK
        assert decision.selected_profile == intent


def test_automation_risk_and_approval() -> None:
    decision = classify("automatizar instalação no sistema")
    assert decision.intent == "automation"
    assert decision.risk in {"medium", "high"}
    assert decision.requires_approval is True
    assert decision.requires_tools is True
    assert decision.constraints.allow_cloud is False


def test_allow_cloud_false_on_all_routes() -> None:
    samples = (
        "bom dia",
        "refatore este código typescript",
        "pesquise no vault o que é D12",
        "agendar cron para executar script",
    )
    for text in samples:
        decision = classify(text)
        assert decision.constraints.allow_cloud is False


def test_invalid_input_returns_structured_error() -> None:
    with pytest.raises(RoutingError, match="entrada inválida|texto vazio"):
        classify("   ")
    with pytest.raises(RoutingError, match="entrada inválida"):
        classify({"request_id": "x", "input_type": "audio", "text": "oi"})
    with pytest.raises(RoutingError, match="entrada inválida"):
        classify({"request_id": "", "text": "oi"})


def test_decision_has_reason_and_confidence() -> None:
    decision = classify("escreva código python para somar")
    assert decision.reason
    assert "intent=coding" in decision.reason
    assert "allow_cloud=false" in decision.reason
    assert 0.0 <= decision.confidence <= 1.0
    assert decision.confidence >= 0.7


def test_knowledge_mentions_rag_capability() -> None:
    decision = classify("o que é RAG no YBY?")
    assert decision.intent == "knowledge"
    assert "rag" in decision.reason.casefold()
    assert decision.requires_tools is False


def test_tools_outside_registry_blocked() -> None:
    with pytest.raises(SafetyViolationError, match="fora do registry"):
        classify("automatizar com shell_run agora")


def test_classify_result_and_request_object() -> None:
    request = Request(request_id="req-42", text="explique o que é um vault")
    result = classify_result(request)
    assert result.request.request_id == "req-42"
    assert result.decision.intent == "knowledge"
    assert result.decision.constraints.allow_cloud is False
    assert "language=pt-BR" in result.decision.reason


def test_high_risk_requires_approval() -> None:
    decision = classify("apagar tudo e formatar disco do servidor")
    assert decision.risk == "high"
    assert decision.requires_approval is True
