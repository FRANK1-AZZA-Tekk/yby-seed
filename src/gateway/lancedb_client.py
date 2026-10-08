"""
LanceDB Client — Vector DB memory-mapped com cache limitado

Responsabilidade:
- Armazenar telemetria + embeddings vetoriais
- Busca por similaridade (RAG)
- Memory-mapping (zero-copy reads)
- Cache limitado (evitar OOM em datasets grandes)

Arquitetura:
[FastAPI worker] → [LanceDB] → [Arquivos no disco] (memory-mapped)

Otimizações:
- index_cache_size=128 (limitar cache em MB)
- prepopulate_cache=False (não carregar tudo na RAM)
- compact_files() periódico (evitar fragmentation)

Licença: Apache 2.0
"""

import lancedb
from datetime import datetime
from typing import List, Dict, Any, Optional
import logging

from .config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LanceDBClient:
    """
    Cliente LanceDB otimizado para Edge AI (4GB VRAM / 16GB RAM).
    """
    
    def __init__(self, db_path: str, index_cache_size: int = 128):
        """
        Inicializar LanceDB.
        
        Args:
            db_path: Caminho para o diretório do banco
            index_cache_size: Tamanho máximo do cache em MB (evitar OOM)
        """
        logger.info(f"🗄️  Inicializando LanceDB em {db_path}...")
        
        self.db = lancedb.connect(
            uri=db_path,
            index_cache_size=index_cache_size,
            prepopulate_cache=False  # Não carregar tudo na RAM
        )
        
        self.metrics_table = None
        self.vectors_table = None
    
    async def init_tables(self):
        """Inicializar tabelas (se não existirem)"""
        
        # Tabela de métricas (armazenamento bruto)
        if "metrics" not in self.db.table_names():
            self.metrics_table = self.db.create_table(
                name="metrics",
                schema={
                    "device_id": str,
                    "timestamp": str,
                    "heart_rate": int,
                    "spo2": int,
                    "battery": int,
                    "steps": int,
                    "context_lat": float,
                    "context_lon": float,
                    "context_activity": str
                }
            )
            logger.info("✅ Tabela 'metrics' criada")
        
        else:
            self.metrics_table = self.db.open_table("metrics")
        
        # Tabela de vetores (embeddings para RAG)
        if "vectors" not in self.db.table_names():
            self.vectors_table = self.db.create_table(
                name="vectors",
                schema={
                    "id": str,
                    "device_id": str,
                    "timestamp": str,
                    "text": str,
                    "vector": "fixed_size_list<float32>[384]",
                    "metadata": str
                }
            )
            logger.info("✅ Tabela 'vectors' criada")
        
        else:
            self.vectors_table = self.db.open_table("vectors")
    
    async def insert_metrics(self, data: Dict[str, Any]):
        """
        Inserir métricas brutas.
        
        Args:
            data: {
                "device_id": "yby-watch-001",
                "timestamp": "2026-10-08T05:20:00Z",
                "metrics": {"heart_rate": 72, "spo2": 98, ...},
                "context": {"location": {...}, "activity": "walking"}
            }
        """
        try:
            row = {
                "device_id": data["device_id"],
                "timestamp": data["timestamp"],
                "heart_rate": data["metrics"].get("heart_rate", 0),
                "spo2": data["metrics"].get("spo2", 0),
                "battery": data["metrics"].get("battery", 0),
                "steps": data["metrics"].get("steps", 0),
                "context_lat": data.get("context", {}).get("location", {}).get("lat", 0.0),
                "context_lon": data.get("context", {}).get("location", {}).get("lon", 0.0),
                "context_activity": data.get("context", {}).get("activity", "unknown")
            }
            
            self.metrics_table.add([row])
            logger.debug(f"✅ Métricas inseridas: {data['device_id']}")
        
        except Exception as e:
            logger.error(f"❌ Erro ao inserir métricas: {e}")
            raise
    
    async def insert_vector(self, data: Dict[str, Any]):
        """
        Inserir embedding vetorial.
        
        Args:
            data: {
                "id": "unique_id",
                "device_id": "yby-watch-001",
                "timestamp": "2026-10-08T05:20:00Z",
                "text": "Backup automation script",
                "vector": [0.1, 0.2, ..., 0.9],  # 384 dimensões
                "metadata": "{\"skill\": \"backup-automation\"}"
            }
        """
        try:
            row = {
                "id": data["id"],
                "device_id": data["device_id"],
                "timestamp": data["timestamp"],
                "text": data["text"],
                "vector": data["vector"],
                "metadata": data.get("metadata", "{}")
            }
            
            self.vectors_table.add([row])
            logger.debug(f"✅ Vetor inserido: {data['id']}")
        
        except Exception as e:
            logger.error(f"❌ Erro ao inserir vetor: {e}")
            raise
    
    async def insert(self, data: Dict[str, Any]):
        """
        Inserir métricas + vetor (transacional).
        
        Args:
            data: {
                "device_id": "yby-watch-001",
                "timestamp": "2026-10-08T05:20:00Z",
                "metrics": {...},
                "context": {...},
                "features": {...},
                "vector": [...]
            }
        """
        # Inserir métricas
        await self.insert_metrics(data)
        
        # Inserir vetor
        import uuid
        await self.insert_vector({
            "id": str(uuid.uuid4()),
            "device_id": data["device_id"],
            "timestamp": data["timestamp"],
            "text": str(data["features"]),
            "vector": data["vector"],
            "metadata": "{\"metrics\": " + str(data["metrics"]) + "}"
        })
    
    async def get_metrics(self, device_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Recuperar últimas N métricas de um dispositivo.
        
        Args:
            device_id: ID do dispositivo
            limit: Número máximo de métricas
        
        Returns:
            Lista de métricas ordenadas por timestamp (desc)
        """
        try:
            results = (
                self.metrics_table
                .search()
                .where(f"device_id = '{device_id}'")
                .order_by("timestamp", order="desc")
                .limit(limit)
                .to_list()
            )
            
            logger.debug(f"✅ Recuperadas {len(results)} métricas de {device_id}")
            return results
        
        except Exception as e:
            logger.error(f"❌ Erro ao recuperar métricas: {e}")
            raise
    
    async def search(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Buscar vetores similares (RAG).
        
        Args:
            query_vector: Vetor de busca (384 dimensões)
            top_k: Número de resultados
        
        Returns:
            Lista de vetores similares com scores
        """
        try:
            results = (
                self.vectors_table
                .search(query_vector)
                .limit(top_k)
                .to_list()
            )
            
            logger.debug(f"✅ Busca vetorial: {len(results)} resultados")
            return results
        
        except Exception as e:
            logger.error(f"❌ Erro na busca vetorial: {e}")
            raise
    
    async def compact(self):
        """
        Compactar arquivos (evitar fragmentation).
        
        Chamar periodicamente (ex: a cada 1 hora).
        """
        try:
            self.db.compact_files()
            logger.info("✅ Arquivos compactados")
        
        except Exception as e:
            logger.error(f"❌ Erro ao compactar: {e}")
    
    async def close(self):
        """Fechar conexões"""
        logger.info("🛑 Fechando LanceDB...")
        # LanceDB não tem close() explícito, mas podemos compactar antes de sair
        await self.compact()
