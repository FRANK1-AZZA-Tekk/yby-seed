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

import asyncio
import json
import logging
from typing import Any, Dict, List

import lancedb

logger = logging.getLogger(__name__)


class LanceDBClient:
    """
    Cliente LanceDB otimizado para Edge AI (4GB VRAM / 16GB RAM).
    """

    def __init__(self, db_path: str, index_cache_size: int = 128):
        """
        Configurar LanceDB com conexão lazy para evitar I/O no import.

        Args:
            db_path: Caminho para o diretório do banco
            index_cache_size: Tamanho máximo do cache em MB (evitar OOM)
        """
        self.db_path = db_path
        self.index_cache_size = index_cache_size
        self.db: Any = None
        self.metrics_table: Any = None
        self.vectors_table: Any = None

    def _ensure_db(self) -> Any:
        if self.db is None:
            logger.info("🗄️  Inicializando LanceDB em %s...", self.db_path)
            self.db = lancedb.connect(
                uri=self.db_path,
                index_cache_size=self.index_cache_size,
                prepopulate_cache=False,  # Não carregar tudo na RAM
            )
        return self.db

    def _init_tables_sync(self) -> None:
        db = self._ensure_db()
        existing = set(db.table_names())

        if "metrics" not in existing:
            self.metrics_table = db.create_table(
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
                    "context_activity": str,
                },
            )
            logger.info("✅ Tabela 'metrics' criada")
        else:
            self.metrics_table = db.open_table("metrics")

        if "vectors" not in existing:
            self.vectors_table = db.create_table(
                name="vectors",
                schema={
                    "id": str,
                    "device_id": str,
                    "timestamp": str,
                    "text": str,
                    "vector": "fixed_size_list<float32>[384]",
                    "metadata": str,
                },
            )
            logger.info("✅ Tabela 'vectors' criada")
        else:
            self.vectors_table = db.open_table("vectors")

    async def init_tables(self):
        """Inicializar tabelas (se não existirem) fora do event loop."""
        await asyncio.to_thread(self._init_tables_sync)

    async def insert_metrics(self, data: Dict[str, Any]):
        """
        Inserir métricas brutas.
        """
        if self.metrics_table is None:
            await self.init_tables()
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
                "context_activity": data.get("context", {}).get("activity", "unknown"),
            }

            await asyncio.to_thread(self.metrics_table.add, [row])
            logger.debug("✅ Métricas inseridas: %s", data["device_id"])

        except Exception as e:
            logger.error("❌ Erro ao inserir métricas: %s", e)
            raise

    async def insert_vector(self, data: Dict[str, Any]):
        """
        Inserir embedding vetorial.
        """
        if self.vectors_table is None:
            await self.init_tables()
        try:
            row = {
                "id": data["id"],
                "device_id": data["device_id"],
                "timestamp": data["timestamp"],
                "text": data["text"],
                "vector": data["vector"],
                "metadata": data.get("metadata", "{}"),
            }

            await asyncio.to_thread(self.vectors_table.add, [row])
            logger.debug("✅ Vetor inserido: %s", data["id"])

        except Exception as e:
            logger.error("❌ Erro ao inserir vetor: %s", e)
            raise

    async def insert(self, data: Dict[str, Any]):
        """
        Inserir métricas + vetor.
        """
        await self.insert_metrics(data)

        import uuid

        await self.insert_vector(
            {
                "id": str(uuid.uuid4()),
                "device_id": data["device_id"],
                "timestamp": data["timestamp"],
                "text": json.dumps(data["features"], ensure_ascii=False),
                "vector": data["vector"],
                "metadata": json.dumps({"metrics": data["metrics"]}, ensure_ascii=False),
            }
        )

    async def get_metrics(self, device_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Recuperar últimas N métricas de um dispositivo.
        """
        if self.metrics_table is None:
            await self.init_tables()
        try:
            safe_device_id = device_id.replace("'", "''")

            def _query() -> List[Dict[str, Any]]:
                return (
                    self.metrics_table.search()
                    .where(f"device_id = '{safe_device_id}'")
                    .order_by("timestamp", order="desc")
                    .limit(limit)
                    .to_list()
                )

            results = await asyncio.to_thread(_query)
            logger.debug("✅ Recuperadas %d métricas de %s", len(results), device_id)
            return results

        except Exception as e:
            logger.error("❌ Erro ao recuperar métricas: %s", e)
            raise

    async def search(self, query_vector: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Buscar vetores similares (RAG).
        """
        if self.vectors_table is None:
            await self.init_tables()
        try:
            def _search() -> List[Dict[str, Any]]:
                return self.vectors_table.search(query_vector).limit(top_k).to_list()

            results = await asyncio.to_thread(_search)
            logger.debug("✅ Busca vetorial: %d resultados", len(results))
            return results

        except Exception as e:
            logger.error("❌ Erro na busca vetorial: %s", e)
            raise

    def _compact_sync(self) -> None:
        for table in (self.metrics_table, self.vectors_table):
            if table is not None and hasattr(table, "compact_files"):
                table.compact_files()

    async def compact(self):
        """
        Compactar arquivos das tabelas (evitar fragmentation).
        """
        try:
            await asyncio.to_thread(self._compact_sync)
            logger.info("✅ Arquivos compactados")
        except Exception as e:
            logger.error("❌ Erro ao compactar: %s", e)

    async def close(self):
        """Fechar conexões"""
        logger.info("🛑 Fechando LanceDB...")
        await self.compact()
