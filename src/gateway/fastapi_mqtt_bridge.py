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

from fastapi import FastAPI, WebSocket, HTTPException
from asyncio import Queue
from typing import List, Dict, Any
import asyncio
import json
from datetime import datetime
import logging

from .lancedb_client import LanceDBClient
from .config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="YBY SEED Gateway",
    description="Gateway IoT para wearables ESP32-S3 com IA local",
    version="1.1.0"
)

# Backpressure queue (max 1000 mensagens)
mqtt_queue: Queue = Queue(maxsize=1000)

# LanceDB client (memory-mapped, cache limitado)
db_client = LanceDBClient(
    db_path=settings.LANCEDB_PATH,
    index_cache_size=128
)

# WebSocket clients (para dashboard em tempo real)
websocket_clients: List[WebSocket] = []


@app.on_event("startup")
async def startup_event():
    """Inicializar DB e iniciar MQTT listener"""
    logger.info("🚀 Inicializando YBY SEED Gateway...")
    
    # Inicializar tabelas LanceDB
    await db_client.init_tables()
    
    # Iniciar MQTT listener em background
    from .mqtt_listener import mqtt_listener
    asyncio.create_task(mqtt_listener(mqtt_queue))
    
    logger.info("✅ Gateway inicializado")


@app.on_event("shutdown")
async def shutdown_event():
    """Fechar conexões"""
    logger.info("🛑 Fechando Gateway...")
    await db_client.close()
    for ws in websocket_clients:
        await ws.close()


@app.post("/telemetry")
async def receive_telemetry(data: Dict[str, Any]):
    """
    Endpoint HTTP para telemetria (fallback se MQTT falhar).
    
    Payload:
    {
        "device_id": "yby-watch-001",
        "timestamp": "2026-10-08T05:20:00Z",
        "metrics": {
            "heart_rate": 72,
            "spo2": 98,
            "battery": 85,
            "steps": 1234
        },
        "context": {
            "location": {"lat": -23.5505, "lon": -46.6333},
            "activity": "walking"
        }
    }
    """
    try:
        # Validar payload mínimo
        required_fields = ["device_id", "timestamp", "metrics"]
        for field in required_fields:
            if field not in data:
                raise HTTPException(status_code=400, detail=f"Campo obrigatório: {field}")
        
        # Enfileirar para processamento assíncrono
        await mqtt_queue.put(data)
        
        return {
            "status": "queued",
            "queue_size": mqtt_queue.qsize(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ Erro ao receber telemetria: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    """
    WebSocket para dashboard em tempo real.
    
    Clientes recebem telemetria processada em tempo real.
    """
    await websocket.accept()
    websocket_clients.append(websocket)
    
    try:
        while True:
            # Aguardar mensagens da queue
            data = await mqtt_queue.get()
            await websocket.send_json(data)
    
    except Exception as e:
        logger.error(f"❌ Erro WebSocket: {e}")
    
    finally:
        websocket_clients.remove(websocket)
        await websocket.close()


@app.get("/health")
async def health_check():
    """Health check do gateway"""
    return {
        "status": "healthy",
        "queue_size": mqtt_queue.qsize(),
        "websocket_clients": len(websocket_clients),
        "timestamp": datetime.utcnow().isoformat()
    }


@app.get("/metrics")
async def get_metrics(device_id: str, limit: int = 100):
    """
    Recuperar últimas N métricas de um dispositivo.
    
    Exemplo: /metrics?device_id=yby-watch-001&limit=100
    """
    try:
        metrics = await db_client.get_metrics(device_id, limit=limit)
        return {
            "device_id": device_id,
            "count": len(metrics),
            "data": metrics
        }
    
    except Exception as e:
        logger.error(f"❌ Erro ao recuperar métricas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vectors/search")
async def search_vectors(query: str, top_k: int = 5):
    """
    Buscar vetores similares no LanceDB (RAG).
    
    Exemplo: /vectors/search?query=backup+automation&top_k=5
    """
    try:
        results = await db_client.search(query, top_k=top_k)
        return {
            "query": query,
            "top_k": top_k,
            "results": results
        }
    
    except Exception as e:
        logger.error(f"❌ Erro ao buscar vetores: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Worker que processa mensagens da queue em batch
@app.on_event("startup")
async def start_worker():
    """Worker que consome mensagens da queue em batch"""
    
    async def worker():
        logger.info("👷 Worker iniciado")
        
        while True:
            # Aguardar batch de 10 mensagens (otimizar throughput)
            batch = []
            try:
                for _ in range(10):
                    data = await asyncio.wait_for(mqtt_queue.get(), timeout=1.0)
                    batch.append(data)
            
            except asyncio.TimeoutError:
                # Timeout: processar batch parcial
                pass
            
            if batch:
                try:
                    # Processar batch em thread pool (evitar bloquear event loop)
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        process_batch,
                        batch
                    )
                    logger.info(f"✅ Batch processado: {len(batch)} mensagens")
                
                except Exception as e:
                    logger.error(f"❌ Erro ao processar batch: {e}")
    
    asyncio.create_task(worker())


def process_batch(batch: List[Dict[str, Any]]):
    """
    Processar batch de telemetria (CPU-bound, roda em thread pool).
    
    - Extrair features
    - Gerar embeddings
    - Armazenar em LanceDB
    """
    for data in batch:
        try:
            # Extrair features
            features = extract_features(data)
            
            # Gerar embedding (modelo local via Ollama)
            embedding = generate_embedding(features)
            
            # Armazenar em LanceDB
            db_client.insert({
                "device_id": data["device_id"],
                "timestamp": data["timestamp"],
                "metrics": data["metrics"],
                "context": data.get("context", {}),
                "features": features,
                "vector": embedding
            })
        
        except Exception as e:
            logger.error(f"❌ Erro ao processar mensagem: {e}")


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


def generate_embedding(features: Dict[str, Any]) -> List[float]:
    """
    Gerar embedding de features (modelo local via Ollama).
    
    Retorna: vetor de 384 dimensões (all-MiniLM-L6-v2)
    """
    # TODO: Implementar com Ollama embeddings
    # Por enquanto, retornar vetor dummy
    return [0.0] * 384
