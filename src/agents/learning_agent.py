"""
Learning Agent — Aprendizado contínuo com PostgreSQL + pgvector

Responsabilidade:
- Armazenar execuções em PostgreSQL (histórico)
- Aprender com feedback do usuário (Bayesian Teaching)
- Sugerir melhorias no sistema (auto-otimização)

Arquitetura:
[Execução] → [PostgreSQL + pgvector] → [Learning Agent] → [Melhorias]

Otimizações:
- Embeddings de execuções (similaridade semântica)
- Bayesian update (atualizar crenças com feedback)
- Auto-otimização (sugerir melhorias baseado em erros)

Licença: MIT
"""

import hashlib
import logging
import math
import os
from typing import Any, Dict, List

import httpx

from ..gateway.config import settings

logger = logging.getLogger(__name__)


class LearningAgent:
    """
    Agente de aprendizado contínuo.
    """
    
    def __init__(self, db_url: str | None = None):
        """
        Inicializar agente.

        A URL vem de YBY_DATABASE_URL. Sem URL, o agente não conecta.
        """
        if db_url is None:
            db_url = os.getenv("YBY_DATABASE_URL", "")
        self.db_url = db_url.strip()
        self.conn = None
        if self.db_url:
            self._connect()

    def _ensure(self) -> Any:
        if self.conn is None:
            self._connect()
        if self.conn is None:
            raise RuntimeError("Conexão PostgreSQL indisponível.")
        return self.conn

    def _connect(self):
        """Conectar ao PostgreSQL"""
        if not self.db_url:
            raise RuntimeError("defina YBY_DATABASE_URL (sem senha no código)")

        import psycopg2
        from pgvector.psycopg2 import register_vector

        logger.info("Conectando PostgreSQL...")

        self.conn = psycopg2.connect(self.db_url)
        register_vector(self.conn)
        
        # Criar tabelas
        self._create_tables()
        
        logger.info("✅ PostgreSQL conectado")
    
    def _create_tables(self):
        """Criar tabelas se não existirem"""
        conn = self._ensure()
        with conn.cursor() as cur:
            # Tabela de execuções
            cur.execute("""
                CREATE TABLE IF NOT EXISTS executions (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMPTZ DEFAULT NOW(),
                    intent VARCHAR(100),
                    slots JSONB,
                    code TEXT,
                    result JSONB,
                    feedback VARCHAR(50),
                    embedding vector(384)
                )
            """)
            
            # Tabela de crenças (Bayesian Teaching)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS beliefs (
                    id SERIAL PRIMARY KEY,
                    key VARCHAR(100) UNIQUE,
                    prior FLOAT,
                    likelihood FLOAT,
                    posterior FLOAT,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            
            # Índice para busca vetorial
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_executions_embedding
                ON executions
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)

            conn.commit()

    def log_execution(
        self,
        intent: str,
        slots: Dict[str, Any],
        code: str,
        result: Dict[str, Any],
        feedback: str | None = None,
    ):
        """
        Logar execução.

        Args:
            intent: Intenção (ex: backup_automation)
            slots: Slots preenchidos
            code: Código gerado
            result: Resultado da execução
            feedback: Feedback do usuário (success, error, neutral)
        """
        conn = self._ensure()
        logger.info("Logando execução: %s", intent)

        embedding = self._generate_embedding(f"{intent} {slots} {code}")

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO executions (intent, slots, code, result, feedback, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (intent, slots, code, result, feedback, embedding),
            )

            conn.commit()

        logger.info("✅ Execução logada")

    def learn_from_feedback(self, execution_id: int, feedback: str):
        """
        Aprender com feedback do usuário.
        """
        conn = self._ensure()
        logger.info("Aprendendo com feedback: %s", feedback)

        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE executions
                SET feedback = %s
                WHERE id = %s
                """,
                (feedback, execution_id),
            )

            conn.commit()

        self._bayesian_update(execution_id, feedback)

        logger.info("✅ Feedback aprendido")

    def _bayesian_update(self, execution_id: int, feedback: str):
        """
        Atualizar crenças com Bayesian Teaching.
        """
        conn = self._ensure()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT intent, slots, result
                FROM executions
                WHERE id = %s
            """, (execution_id,))
            
            row = cur.fetchone()
            if row is None:
                logger.warning(
                    "Execução %s não encontrada para atualização bayesiana",
                    execution_id,
                )
                return
            intent, slots, result = row
        
        # Calcular likelihood (probabilidade do feedback dado a crença)
        likelihood = 0.9 if feedback == "success" else 0.1
        
        # Obter crença anterior (prior)
        prior = self._get_belief(f"intent_{intent}")
        
        # Calcular posterior (Bayes)
        posterior = (likelihood * prior) / ((likelihood * prior) + ((1 - likelihood) * (1 - prior)))
        
        # Atualizar crença
        self._update_belief(f"intent_{intent}", prior, likelihood, posterior)
        
        logger.info(f"✅ Bayesian update: {intent} (prior={prior:.2f}, likelihood={likelihood:.2f}, posterior={posterior:.2f})")
    
    def _get_belief(self, key: str) -> float:
        """
        Obter crença (prior).
        """
        conn = self._ensure()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT prior
                FROM beliefs
                WHERE key = %s
            """, (key,))

            row = cur.fetchone()
            return row[0] if row else 0.5  # Default: 0.5 (incerteza)

    def _update_belief(self, key: str, prior: float, likelihood: float, posterior: float):
        """
        Atualizar crença.
        """
        conn = self._ensure()
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO beliefs (key, prior, likelihood, posterior)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (key)
                DO UPDATE SET
                    prior = EXCLUDED.posterior,
                    likelihood = EXCLUDED.likelihood,
                    posterior = EXCLUDED.posterior,
                    updated_at = NOW()
            """, (key, prior, likelihood, posterior))

            conn.commit()

    def suggest_improvements(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Sugerir melhorias baseado em erros.
        """
        conn = self._ensure()
        logger.info("Sugerindo melhorias (top %d)...", limit)

        with conn.cursor() as cur:
            # Buscar execuções com erro
            cur.execute("""
                SELECT intent, slots, code, result
                FROM executions
                WHERE feedback = 'error'
                ORDER BY timestamp DESC
                LIMIT %s
            """, (limit,))
            
            errors = cur.fetchall()
            
            # Gerar sugestões
            suggestions = []
            
            for intent, slots, code, result in errors:
                suggestion = self._generate_suggestion(intent, slots, code, result)
                suggestions.append(suggestion)
            
            logger.info(f"✅ {len(suggestions)} sugestões geradas")
            return suggestions
    
    def _generate_suggestion(self, intent: str, slots: Dict, code: str, result: Dict) -> Dict[str, Any]:
        """
        Gerar sugestão de melhoria.
        
        Args:
            intent: Intenção
            slots: Slots
            code: Código
            result: Resultado com erro
        
        Returns:
            Sugestão
        """
        # Analisar erro
        error_message = result.get("error", "Unknown error")
        
        # Gerar sugestão baseada no erro
        if "timeout" in error_message.lower():
            suggestion = f"Aumentar timeout para {intent} (atual: 30s, sugerido: 60s)"
        
        elif "memory" in error_message.lower():
            suggestion = f"Otimizar uso de memória em {intent} (reduzir batch size, usar generators)"
        
        elif "permission" in error_message.lower():
            suggestion = f"Verificar permissões para {intent} (chmod, chown, sudo)"
        
        else:
            suggestion = f"Revisar código de {intent}: {error_message[:100]}"
        
        return {
            "intent": intent,
            "error": error_message,
            "suggestion": suggestion,
            "priority": "high" if "timeout" in error_message.lower() else "medium"
        }
    
    def _generate_embedding(self, text: str) -> List[float]:
        """
        Gerar embedding via Ollama local com fallback determinístico normalizado.
        """
        url = f"{settings.OLLAMA_HOST.rstrip('/')}/api/embeddings"
        try:
            response = httpx.post(
                url,
                json={"model": settings.OLLAMA_MODEL_EMBEDDING, "prompt": text},
                timeout=10.0,
            )
            response.raise_for_status()
            raw = response.json().get("embedding")
            if isinstance(raw, list) and raw:
                return [float(x) for x in raw]
        except Exception as exc:
            logger.warning("Ollama embeddings indisponível em LearningAgent (%s); usando fallback.", type(exc).__name__)

        values: List[float] = []
        counter = 0
        while len(values) < 384:
            digest = hashlib.sha256(f"{counter}:{text}".encode("utf-8")).digest()
            for idx in range(0, len(digest), 4):
                if len(values) >= 384:
                    break
                chunk = int.from_bytes(digest[idx : idx + 4], "big", signed=False)
                values.append((chunk / 0xFFFFFFFF) * 2.0 - 1.0)
            counter += 1
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]
    
    def close(self):
        """Fechar conexão"""
        if self.conn:
            self.conn.close()
            logger.info("🛑 PostgreSQL desconectado")


# Instância global
learning_agent = LearningAgent()


if __name__ == "__main__":
    # Logar execução
    learning_agent.log_execution(
        intent="backup_automation",
        slots={"source": "/home/user/docs", "dest": "/backup"},
        code="import zipfile; ...",
        result={"success": True},
        feedback="success"
    )
    
    # Aprender com feedback
    learning_agent.learn_from_feedback(execution_id=1, feedback="success")
    
    # Sugerir melhorias
    suggestions = learning_agent.suggest_improvements(limit=5)
    
    print(f"\n🧠 Sugestões ({len(suggestions)}):")
    for s in suggestions:
        print(f"- {s['suggestion']}")
    
    # Fechar
    learning_agent.close()
