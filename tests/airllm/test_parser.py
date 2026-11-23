import pytest
from src.airllm.parser import extract_json, parse_json


def test_json_puro():
    assert extract_json('{"a": 1}') == '{"a": 1}'


def test_json_em_markdown():
    text = "Aqui está:\n```json\n{\"b\": 2}\n```"
    assert extract_json(text) == '{"b": 2}'


def test_json_malformado():
    assert extract_json("sem json aqui") is None


def test_parse_json_com_schema():
    schema = {"required": ["resumo"]}
    obj = parse_json('{"resumo": "teste"}', schema=schema)
    assert obj["resumo"] == "teste"


def test_parse_json_retry():
    calls = []
    def retry():
        calls.append(1)
        return '{"ok": true}'
    obj = parse_json("lixo", schema={"required": ["ok"]}, retry_fn=retry, max_retries=1)
    assert obj["ok"] is True
    assert len(calls) == 1
