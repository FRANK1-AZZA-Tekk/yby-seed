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

import psycopg2
from psycopg2.extras import execute_values
import pgvector
from pgvector.psycopg2 import register_vector
from typing import Dict, Any, List
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LearningAgent:
    """
    Agente de aprendizado contínuo.
    """
    
    def __init__(self, db_url: str = "postgresql://yby:yby_seed_password@localhost:5432/yby_seed"):
        """
        Inicializar agente.
        
        Args:
            db_url: URL do PostgreSQL
        """
        self.db_url = db_url
        self.conn = None
        self._connect()
    
    def _connect(self):
        """Conectar ao PostgreSQL"""
        logger.info("🧠 Conectando PostgreSQL...")
        
        self.conn = psycopg2.connect(self.db_url)
        register_vector(self.conn)
        
        # Criar tabelas
        self._create_tables()
        
        logger.info("✅ PostgreSQL conectado")
    
    def _create_tables(self):
        """Criar tabelas se não existirem"""
        with self.conn.cursor() as cur:
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
            
            self.conn.commit()
    
    def log_execution(self, intent: str, slots: Dict, code: str, result: Dict, feedback: str = None):
        """
        Logar execução.
        
        Args:
            intent: Intenção (ex: backup_automation)
            slots: Slots preenchidos
            code: Código gerado
            result: Resultado da execução
            feedback: Feedback do usuário (success, error, neutral)
        """
        logger.info(f"🧠 Logando execução: {intent}")
        
        # Gerar embedding da execução
        embedding = self._generate_embedding(f"{intent} {slots} {code}")
        
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO executions (intent, slots, code, result, feedback, embedding)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (intent, slots, code, result, feedback, embedding))
            
            self.conn.commit()
        
        logger.info("✅ Execução logada")
    
    def learn_from_feedback(self, execution_id: int, feedback: str):
        """
        Aprender com feedback do usuário.
        
        Args:
            execution_id: ID da execução
            feedback: Feedback (success, error, neutral)
        """
        logger.info(f"🧠 Aprendendo com feedback: {feedback}")
        
        # Atualizar feedback
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE executions
                SET feedback = %s
                WHERE id = %s
            """, (feedback, execution_id))
            
            self.conn.commit()
        
        # Bayesian update
        self._bayesian_update(execution_id, feedback)
        
        logger.info("✅ Feedback aprendido")
    
    def _bayesian_update(self, execution_id: int, feedback: str):
        """
        Atualizar crenças com Bayesian Teaching.
        
        Args:
            execution_id: ID da execução
            feedback: Feedback (success, error)
        """
        # Obter execução
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT intent, slots, result
                FROM executions
                WHERE id = %s
            """, (execution_id,))
            
            row = cur.fetchone()
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
        
        Args:
            key: Chave da crença
        
        Returns:
            Valor do prior (0.0-1.0)
        """
        with self.conn.cursor() as cur:
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
        
        Args:
            key: Chave da crença
            prior: Prior anterior
            likelihood: Likelihood calculada
            posterior: Posterior calculado
        """
        with self.conn.cursor() as cur:
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
            
            self.conn.commit()
    
    def suggest_improvements(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Sugerir melhorias baseado em erros.
        
        Args:
            limit: Número máximo de sugestões
        
        Returns:
            Lista de sugestões
        """
        logger.info(f"🧠 Sugerindo melhorias (top {limit})...")
        
        with self.conn.cursor() as cur:
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
        Gerar embedding (modelo local via Ollama).
        
        Args:
            text: Texto para embedar
        
        Returns:
            Vetor de 384 dimensões
        """
        # TODO: Implementar com Ollama embeddings
        # Por enquanto, retornar vetor dummy
        return [0.0] * 384
    
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
