"""Testes do gateway (FastAPI + MQTT + LanceDB).

Estes testes dependem de serviços externos (Ollama, PostgreSQL, MQTT, LanceDB).
Por enquanto, estão marcados como skip até que fixtures reais sejam implementadas.
"""

import pytest


@pytest.mark.skip(reason="Gateway depende de Ollama/PostgreSQL/MQTT - fixtures pendentes")
@pytest.mark.integration
async def test_gateway_recebe_comando_e_retorna_id(sample_user_command, mock_mqtt_client, mock_lancedb):
    """Gateway deve receber comando e retornar ID de tarefa."""
    # TODO: Implementar testes reais quando fixtures estiverem prontas
    pass


@pytest.mark.skip(reason="Gateway depende de Ollama/PostgreSQL/MQTT - fixtures pendentes")
@pytest.mark.integration
async def test_gateway_publica_no_mqtt(mock_mqtt_client):
    """Gateway deve publicar mensagem no tópico MQTT correto."""
    # TODO: Implementar testes reais quando fixtures estiverem prontas
    pass


@pytest.mark.skip(reason="Gateway depende de Ollama/PostgreSQL/MQTT - fixtures pendentes")
@pytest.mark.integration
async def test_gateway_armazena_no_lancedb(mock_lancedb):
    """Gateway deve armazenar embeddings no LanceDB."""
    # TODO: Implementar testes reais quando fixtures estiverem prontas
    pass
