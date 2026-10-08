"""Fixtures e configuração de testes para o YBY SEED.

Regras:
- Nenhum teste depende de serviços externos (Ollama, PostgreSQL, MQTT).
- Testes de integração (gateway, RAG) são marcados com @pytest.mark.skip
  até que fixtures reais sejam implementadas.
- Foco em testes unitários dos agentes e lógica pura.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ============================================================================
# FIXTURES GERAIS
# ============================================================================


@pytest.fixture
def mock_llm_client():
    """Mock do cliente LLM (Ollama/LiteLLM) para testes unitários."""
    with patch("src.agents.router_agent.LLMClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.generate = AsyncMock(return_value="mocked response")
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_mqtt_client():
    """Mock do cliente MQTT para testes de gateway."""
    with patch("src.gateway.mqtt_listener.mqtt.Client") as mock_client:
        mock_instance = MagicMock()
        mock_instance.connect = MagicMock(return_value=0)
        mock_instance.subscribe = MagicMock()
        mock_instance.publish = MagicMock()
        mock_client.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_lancedb():
    """Mock do LanceDB para testes de RAG."""
    with patch("src.gateway.lancedb_client.lancedb.connect") as mock_connect:
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_table.search = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        mock_table.add = AsyncMock()
        mock_db.open_table = MagicMock(return_value=mock_table)
        mock_connect.return_value = mock_db
        yield mock_db


# ============================================================================
# DADOS DE TESTE
# ============================================================================


@pytest.fixture
def sample_user_command():
    """Comando de usuário de exemplo para testes."""
    return {
        "command": "Me avise se chover amanhã",
        "user_id": "test_user_001",
        "timestamp": "2026-10-08T09:00:00Z",
    }


@pytest.fixture
def sample_skill_manifest():
    """Manifesto de skill de exemplo para testes."""
    return {
        "name": "weather_alert",
        "version": "1.0.0",
        "description": "Alerta de chuva via API do clima",
        "entry_point": "main",
        "permissions": ["network", "notification"],
    }


# ============================================================================
# MARCADORES DE TESTE
# ============================================================================


def pytest_configure(config):
    """Registrar marcadores personalizados."""
    config.addinivalue_line("markers", "skip: marcar teste como skip (integração pendente)")
    config.addinivalue_line("markers", "unit: teste unitário (sem dependências externas)")
    config.addinivalue_line("markers", "integration: teste de integração (requer serviços)")
