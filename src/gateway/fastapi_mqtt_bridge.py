"""
Gateway YBY SEED — FastAPI + MQTT Bridge com Backpressure

Responsabilidade:
- Receber telemetria MQTT de wearables (ESP32-S3)
- Enfileirar mensagens com backpressure (asyncio.Queue)
- Processar em thread pool separado (evitar freeze do event loop)
- Armazenar em LanceDB (vector DB memory-mapped)

Arquitetura:
[ESP32-S3] → [MQTT Broker] → [mqtt_listener.py] → [asyncio.Queue] → [FastAPI worker] → [LanceDB]

Backpressure:
- Queue maxsize=1000 (evita OOM)
- Worker consome 10 msgs/batch (throughput otimizado)
- LanceDB index_cache_size=128 (evita OOM em datasets grandes)

Licença: MIT
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, HTTPException
from asyncio import Queue
from typing import List, Dict, Any
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import logging
import math

import httpx

from .lancedb_client import LanceDBClient
from .auth import check_token
from .config import settings

logger = logging.getLogger(__name__)

# Backpressure queue (max 1000 mensagens)
mqtt_queue: Queue = Queue(maxsize=1000)

# LanceDB client (memory-mapped, cache limitado)
db_client = LanceDBClient(
    db_path=settings.LANCEDB_PATH,
    index_cache_size=128
)

# WebSocket clients (para dashboard em tempo real)
websocket_clients: List[WebSocket] = []
_ws_queues: Dict[WebSocket, Queue] = {}


async def _telemetry_worker() -> None:
    """Worker que consome mensagens da queue em batch."""
    logger.info("👷 Worker iniciado")
    while True:
        batch = []
        try:
            for _ in range(10):
                data = await asyncio.wait_for(mqtt_queue.get(), timeout=1.0)
                batch.append(data)
        except asyncio.TimeoutError:
            pass

        if batch:
            try:
                await process_batch(batch)
                logger.info("✅ Batch processado: %d mensagens", len(batch))
            except Exception as e:
                logger.error("❌ Erro ao processar batch: %s", e)
            finally:
                for _ in batch:
                    mqtt_queue.task_done()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Inicializa DB/listeners no startup e encerra tarefas/conexões no shutdown."""
    logger.info("🚀 Inicializando YBY SEED Gateway...")
    await db_client.init_tables()

    from .mqtt_listener import mqtt_listener

    tasks = [
        asyncio.create_task(mqtt_listener(mqtt_queue)),
        asyncio.create_task(_telemetry_worker()),
    ]
    logger.info("✅ Gateway inicializado")
    try:
        yield
    finally:
        logger.info("🛑 Fechando Gateway...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await db_client.close()
        for ws in list(websocket_clients):
            _ws_queues.pop(ws, None)
            try:
                await ws.close()
            except Exception:  # noqa: BLE001
                pass
        websocket_clients.clear()


app = FastAPI(
    title="YBY SEED Gateway",
    description="Gateway IoT para wearables ESP32-S3 com IA local",
    version="1.1.0",
    lifespan=lifespan,
)


def _guard(headers) -> None:
    allowed, status, detail = check_token(headers, settings.GATEWAY_TOKEN)
    if not allowed:
        raise HTTPException(status_code=status, detail=detail)


@app.post("/telemetry")
async def receive_telemetry(data: Dict[str, Any], request: Request):
    """
    Endpoint HTTP para telemetria (fallback se MQTT falhar).
    """
    _guard(request.headers)
    try:
        # Validar payload mínimo
        required_fields = ["device_id", "timestamp", "metrics"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Campo obrigatório: {field}")

        # Enfileirar para processamento assíncrono com backpressure não bloqueante
        try:
            mqtt_queue.put_nowait(data)
        except asyncio.QueueFull as exc:
            raise HTTPException(status_code=503, detail="Fila de telemetria cheia") from exc

        return {
            "status": "queued",
            "queue_size": mqtt_queue.qsize(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception("❌ Erro ao receber telemetria")
        raise HTTPException(status_code=500, detail="Erro interno ao processar telemetria.")


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    """WebSocket para dashboard em tempo real."""
    allowed, _status, _detail = check_token(websocket.headers, settings.GATEWAY_TOKEN)
    if not allowed:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    client_queue: Queue = Queue(maxsize=100)
    websocket_clients.append(websocket)
    _ws_queues[websocket] = client_queue

    try:
        while True:
            data = await client_queue.get()
            await websocket.send_json(data)

    except Exception as e:
        logger.error(f"❌ Erro WebSocket: {e}")

    finally:
        _ws_queues.pop(websocket, None)
        if websocket in websocket_clients:
            websocket_clients.remove(websocket)
        try:
            await websocket.close()
        except Exception:  # noqa: BLE001
            pass


@app.get("/health")
async def health_check():
    """Health check do gateway"""
    return {
        "status": "healthy",
        "queue_size": mqtt_queue.qsize(),
        "websocket_clients": len(websocket_clients),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/metrics")
async def get_metrics(device_id: str, request: Request, limit: int = 100):
    """Recuperar últimas N métricas de um dispositivo."""
    _guard(request.headers)
    if not device_id.strip():
        raise HTTPException(status_code=400, detail="device_id obrigatório.")
    if not 1 <= limit <= 1000:
        raise HTTPException(status_code=400, detail="limit deve estar entre 1 e 1000.")
    try:
        metrics = await db_client.get_metrics(device_id, limit=limit)
        return {
            "device_id": device_id,
            "count": len(metrics),
            "data": metrics,
        }

    except Exception:
        logger.exception("❌ Erro ao recuperar métricas")
        raise HTTPException(status_code=500, detail="Erro interno ao recuperar métricas.")


@app.post("/vectors/search")
async def search_vectors(query: str, request: Request, top_k: int = 5):
    """Buscar vetores similares no LanceDB (RAG)."""
    _guard(request.headers)
    clean_query = query.strip()
    if not clean_query:
        raise HTTPException(status_code=400, detail="query obrigatória.")
    if not 1 <= top_k <= 100:
        raise HTTPException(status_code=400, detail="top_k deve estar entre 1 e 100.")
    try:
        query_vector = await asyncio.to_thread(
            generate_embedding,
            {"query": clean_query},
            allow_fallback=False,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Serviço de embeddings indisponível.") from exc
    try:
        results = await db_client.search(query_vector, top_k=top_k)
        return {
            "query": clean_query,
            "top_k": top_k,
            "results": results,
        }

    except Exception:
        logger.exception("❌ Erro ao buscar vetores")
        raise HTTPException(status_code=500, detail="Erro interno na busca vetorial.")


async def process_batch(batch: List[Dict[str, Any]]) -> None:
    """
    Processar batch de telemetria no event loop.

    - Extrair features
    - Gerar embeddings
    - Armazenar em LanceDB (``await`` obrigatório)
    """
    for data in batch:
        try:
            features = extract_features(data)
            embedding = await asyncio.to_thread(generate_embedding, features)
            await db_client.insert(
                {
                    "device_id": data["device_id"],
                    "timestamp": data["timestamp"],
                    "metrics": data["metrics"],
                    "context": data.get("context", {}),
                    "features": features,
                    "vector": embedding,
                }
            )
            for client_queue in list(_ws_queues.values()):
                try:
                    client_queue.put_nowait(data)
                except asyncio.QueueFull:
                    pass
        except Exception as e:
            logger.error("❌ Erro ao processar mensagem: %s", e)
            raise


def extract_features(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrair features relevantes da telemetria para RAG.
    
    Features:
    - Média móvel de batimentos (últimos 5 minutos)
    - Tendência de SpO2 (subindo/descendo)
    - Nível de atividade (sedentário/leve/moderado/intenso)
    - Padrão de sono (se aplicável)
    """
    metrics = data["metrics"]
    
    features = {
        "heart_rate_avg": metrics.get("heart_rate", 0),
        "spo2_trend": "stable",  # Calcular com histórico
        "activity_level": "unknown",  # Calcular com acelerômetro
        "battery_low": metrics.get("battery", 100) < 20,
        "steps_today": metrics.get("steps", 0)
    }
    
    return features


def _deterministic_fallback_embedding(text: str, dims: int = 384) -> List[float]:
    values: List[float] = []
    counter = 0
    while len(values) < dims:
        digest = hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
        for idx in range(0, len(digest), 4):
            if len(values) >= dims:
                break
            chunk = int.from_bytes(digest[idx : idx + 4], "big", signed=False)
            values.append((chunk / 0xFFFFFFFF) * 2.0 - 1.0)
        counter += 1
    norm = math.sqrt(sum(v * v for v in values)) or 1.0
    return [v / norm for v in values]


def generate_embedding(features: Dict[str, Any], *, allow_fallback: bool = True) -> List[float]:
    """
    Gerar embedding de features via Ollama local (/api/embeddings).

    Quando ``allow_fallback=True`` (ingestão offline), degrada para projeção
    determinística normalizada de 384 dimensões se o Ollama não responder.
    """
    prompt = json.dumps(features, ensure_ascii=False, sort_keys=True)
    url = f"{settings.OLLAMA_HOST.rstrip('/')}/api/embeddings"
    try:
        response = httpx.post(
            url,
            json={"model": settings.OLLAMA_MODEL_EMBEDDING, "prompt": prompt},
            timeout=10.0,
        )
        response.raise_for_status()
        payload = response.json()
        raw = payload.get("embedding")
        if not isinstance(raw, list) or not raw:
            raise ValueError("Resposta Ollama sem campo 'embedding' válido.")
        return [float(x) for x in raw]
    except Exception as exc:
        if not allow_fallback:
            raise RuntimeError(f"Falha ao gerar embedding no Ollama: {exc}") from exc
        logger.warning("Ollama embeddings indisponível (%s); usando fallback determinístico.", type(exc).__name__)
        return _deterministic_fallback_embedding(prompt)


def main() -> None:
    """Sobe o gateway só no host configurado. O padrão é 127.0.0.1."""

    import uvicorn

    uvicorn.run(app, host=settings.FASTAPI_HOST, port=settings.FASTAPI_PORT)


if __name__ == "__main__":
    main()
