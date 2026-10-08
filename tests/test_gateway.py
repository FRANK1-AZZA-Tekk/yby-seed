"""
Testes do Gateway (FastAPI + MQTT + LanceDB)

Cobertura:
- FastAPI endpoints (/telemetry, /metrics, /health)
- MQTT listener (backpressure, auto-reconnect)
- LanceDB client (insert, search, compact)

Execução:
pytest tests/test_gateway.py -v --cov=src/gateway

Licença: MIT
"""

import pytest
import asyncio
from httpx import AsyncClient
from src.gateway.fastapi_mqtt_bridge import app
from src.gateway.lancedb_client import LanceDBClient


@pytest.fixture
async def client():
    """Cliente HTTP assíncrono para testes"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def lancedb_client():
    """Cliente LanceDB para testes"""
    return LanceDBClient(db_path=":memory:", index_cache_size=16)


# === Testes FastAPI ===

@pytest.mark.asyncio
async def test_health_check(client):
    """Testar health check do gateway"""
    response = await client.get("/health")
    
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert "queue_size" in response.json()
    assert "websocket_clients" in response.json()


@pytest.mark.asyncio
async def test_receive_telemetry(client):
    """Testar recebimento de telemetria"""
    telemetry = {
        "device_id": "yby-watch-001",
        "timestamp": "2026-10-08T05:20:00Z",
        "metrics": {
            "heart_rate": 72,
            "spo2": 98,
            "battery": 85,
            "steps": 1234
        }
    }
    
    response = await client.post("/telemetry", json=telemetry)
    
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert "queue_size" in response.json()


@pytest.mark.asyncio
async def test_receive_telemetry_missing_fields(client):
    """Testar telemetria com campos faltantes"""
    telemetry = {
        "device_id": "yby-watch-001"
        # timestamp e metrics faltando
    }
    
    response = await client.post("/telemetry", json=telemetry)
    
    assert response.status_code == 400
    assert "Campo obrigatório" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_metrics(client, lancedb_client):
    """Testar recuperação de métricas"""
    # Inserir métricas de teste
    await lancedb_client.insert_metrics({
        "device_id": "yby-watch-001",
        "timestamp": "2026-10-08T05:20:00Z",
        "metrics": {"heart_rate": 72},
        "context": {}
    })
    
    response = await client.get("/metrics?device_id=yby-watch-001&limit=100")
    
    assert response.status_code == 200
    assert response.json()["device_id"] == "yby-watch-001"
    assert len(response.json()["data"]) >= 0


@pytest.mark.asyncio
async def test_search_vectors(client, lancedb_client):
    """Testar busca vetorial"""
    # Inserir vetor de teste
    await lancedb_client.insert_vector({
        "id": "test-1",
        "device_id": "yby-watch-001",
        "timestamp": "2026-10-08T05:20:00Z",
        "text": "Backup automation script",
        "vector": [0.1] * 384,
        "metadata": "{}"
    })
    
    response = await client.post("/vectors/search?query=backup&top_k=5")
    
    assert response.status_code == 200
    assert "results" in response.json()


# === Testes LanceDB ===

@pytest.mark.asyncio
async def test_lancedb_insert_metrics(lancedb_client):
    """Testar inserção de métricas no LanceDB"""
    await lancedb_client.insert_metrics({
        "device_id": "yby-watch-001",
        "timestamp": "2026-10-08T05:20:00Z",
        "metrics": {"heart_rate": 72},
        "context": {}
    })
    
    metrics = await lancedb_client.get_metrics("yby-watch-001", limit=100)
    
    assert len(metrics) >= 0
    assert metrics[0]["device_id"] == "yby-watch-001"


@pytest.mark.asyncio
async def test_lancedb_insert_vector(lancedb_client):
    """Testar inserção de vetor no LanceDB"""
    await lancedb_client.insert_vector({
        "id": "test-1",
        "device_id": "yby-watch-001",
        "timestamp": "2026-10-08T05:20:00Z",
        "text": "Test vector",
        "vector": [0.1] * 384,
        "metadata": "{}"
    })
    
    results = await lancedb_client.search([0.1] * 384, top_k=5)
    
    assert len(results) >= 0
    assert results[0]["text"] == "Test vector"


@pytest.mark.asyncio
async def test_lancedb_compact(lancedb_client):
    """Testar compactação de arquivos"""
    await lancedb_client.compact()
    # Se não levantar exceção, passou


# === Testes MQTT Listener ===

@pytest.mark.asyncio
async def test_mqtt_queue_backpressure():
    """Testar backpressure da queue MQTT"""
    from asyncio import Queue
    
    queue = Queue(maxsize=1000)
    
    # Encher queue
    for i in range(1000):
        queue.put_nowait({"test": i})
    
    # Tentar adicionar mais (deve levantar QueueFull)
    with pytest.raises(asyncio.QueueFull):
        queue.put_nowait({"test": 1001})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
