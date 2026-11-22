"""Testes do extrator JSON compartilhado."""

from src.core.json_extract import extract_json_object


def test_extrai_objeto_simples():
    assert extract_json_object('{"a": 1}') == {"a": 1}


def test_extrai_com_fence():
    text = '```json\n{"agent": "planning", "intent": "x"}\n```'
    assert extract_json_object(text)["agent"] == "planning"


def test_extrai_aninhado():
    text = 'prefix {"a": {"b": 1}, "c": true} suffix'
    assert extract_json_object(text) == {"a": {"b": 1}, "c": True}


def test_vazio():
    assert extract_json_object("") is None
    assert extract_json_object("sem json") is None
