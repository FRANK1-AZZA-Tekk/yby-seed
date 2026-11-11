"""Imports do gateway/RAG/monitoring não devem explodir sem deps pesadas."""

import pytest
from src.gateway.lancedb_client import safe_device_id


def test_import_gateway_config():
    from src.gateway.config import Settings, settings

    assert settings.OLLAMA_HOST
    s = Settings.from_env()
    assert s.MQTT_BROKER_PORT == 1883


def test_import_ast_chunker_sem_treesitter():
    from src.rag.ast_chunker import get_ast_chunker

    chunker = get_ast_chunker()
    chunks = chunker.chunk("def hello():\n    return 1\n", max_tokens=64)
    assert chunks
    assert chunks[0]["code"]


def test_import_rag_optimizer_lazy():
    from src.rag.rag_optimizer import get_rag_optimizer

    rag = get_rag_optimizer()
    assert rag.db_path


def test_import_monitoring_no_server():
    from src.monitoring.metrics_dashboard import get_metrics_dashboard

    dash = get_metrics_dashboard(start_server=False)
    assert dash._started is False


def test_lancedb_safe_device_id():
    assert safe_device_id("yby-watch-001") == "yby-watch-001"
    with pytest.raises(ValueError):
        safe_device_id("'; DROP TABLE metrics; --")
