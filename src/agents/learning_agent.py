#!/usr/bin/env python3
"""
Learning Agent - Auto-evolução diária baseada em feedback do usuário

Uso:
    learner = LearningAgent(sqlite_db)
    learner.learn_from_feedback(user_feedback, error_log)
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from loguru import logger
import sqlite3


class LearningAgent:
    """Agente de aprendizado contínuo"""
    
    def __init__(self, db_path: str = "/opt/yby/registry/yby_seeds.db"):
        self.db_path = db_path
        self._init_db()
        logger.info("🧠 Learning Agent inicializado")
    
    def _init_db(self):
        """Inicializa tabela de aprendizado"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS learning_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            user_feedback TEXT NOT NULL,
            error_log TEXT,
            lesson_learned TEXT,
            applied_to_prd TEXT,
            status TEXT DEFAULT 'pending'
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            total_events INTEGER,
            lessons_learned INTEGER,
            optimizations_applied INTEGER,
            report_json TEXT
        )
        """)
        
        conn.commit()
        conn.close()
    
    def learn_from_feedback(
        self,
        user_feedback: str,
        error_log: str = "",
        prd_id: str = ""
    ) -> Dict[str, Any]:
        """Aprende de feedback do usuário"""
        
        logger.info("📚 Aprendendo de feedback...")
        
        # Salva evento de aprendizado
        event_id = self._save_learning_event(
            user_feedback,
            error_log,
            prd_id
        )
        
        # Gera lição aprendida (usando Ollama)
        lesson = self._generate_lesson(user_feedback, error_log)
        
        # Atualiza evento com lição
        self._update_event(event_id, lesson)
        
        # Verifica se deve aplicar otimizações
        should_optimize = self._should_apply_optimization(user_feedback)
        
        if should_optimize:
            # Gera relatório de otimização
            optimization_report = self._generate_optimization_report()
            
            return {
                "event_id": event_id,
                "lesson_learned": lesson,
                "optimization_report": optimization_report,
                "status": "optimization_pending"
            }
        
        return {
            "event_id": event_id,
            "lesson_learned": lesson,
            "status": "learned"
        }
    
    def _save_learning_event(
        self,
        feedback: str,
        error_log: str,
        prd_id: str
    ) -> int:
        """Salva evento de aprendizado no DB"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO learning_events
        (timestamp, user_feedback, error_log, applied_to_prd)
        VALUES (?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            feedback,
            error_log,
            prd_id
        ))
        
        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return event_id
    
    def _generate_lesson(self, feedback: str, error_log: str) -> str:
        """Gera lição aprendida do erro"""
        
        from src.core.ollama_client import OllamaClient
        ollama = OllamaClient()
        
        prompt = f"""
Feedback do usuário: {feedback}
Log de erro: {error_log}

Extraia UMA lição aprendida clara e acionável.
Formato: "Sempre [ação] quando [condição] para evitar [problema]."
Exemplo: "Sempre validar API key antes de usar para evitar falhas de autenticação."
"""
        
        lesson = ollama.generate(
            model="llama3.2:3b-instruct-q4_K_M",
            prompt=prompt,
            options={"temperature": 0.2, "num_predict": 256}
        )
        
        return lesson.strip()
    
    def _update_event(self, event_id: int, lesson: str):
        """Atualiza evento com lição aprendida"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        UPDATE learning_events
        SET lesson_learned = ?, status = 'learned'
        WHERE id = ?
        """, (lesson, event_id))
        
        conn.commit()
        conn.close()
    
    def _should_apply_optimization(self, feedback: str) -> bool:
        """Decide se aplica otimização baseada no feedback"""
        
        # Padrões que indicam necessidade de otimização
        optimization_keywords = [
            "lento",
            "demorado",
            "ineficiente",
            "poderia ser melhor",
            "muitos passos",
            "complicado"
        ]
        
        return any(keyword in feedback.lower() for keyword in optimization_keywords)
    
    def _generate_optimization_report(self) -> Dict[str, Any]:
        """Gera relatório de otimizações sugeridas"""
        
        from src.core.ollama_client import OllamaClient
        ollama = OllamaClient()
        
        # Busca eventos recentes
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT user_feedback, error_log, lesson_learned
        FROM learning_events
        WHERE timestamp > datetime('now', '-7 days')
        AND status = 'learned'
        """)
        
        events = cursor.fetchall()
        conn.close()
        
        if not events:
            return {"optimizations": []}
        
        # Gera relatório
        events_text = "\n".join([
            f"Feedback: {e[0]}\nErro: {e[1]}\nLição: {e[2]}"
            for e in events
        ])
        
        prompt = f"""
Eventos de aprendizado dos últimos 7 dias:
{events_text}

Gere 3-5 otimizações acionáveis para o sistema.
Formato JSON:
{{
    "optimizations": [
        {{
            "title": "Título",
            "description": "Descrição",
            "impact": "Alto/Médio/Baixo",
            "effort": "Baixo/Médio/Alto"
        }}
    ]
}}
"""
        
        report_json = ollama.generate(
            model="llama3.2:3b-instruct-q4_K_M",
            prompt=prompt,
            options={"temperature": 0.2, "num_predict": 1024}
        )
        
        import json
        import re
        
        json_match = re.search(r'\{[^}]+\}', report_json, re.DOTALL)
        
        if json_match:
            return json.loads(json_match.group())
        
        return {"optimizations": []}
    
    def generate_daily_report(self, date: str = None) -> Dict[str, Any]:
        """Gera relatório diário de aprendizado"""
        
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Conta eventos do dia
        cursor.execute("""
        SELECT COUNT(*), COUNT(lesson_learned)
        FROM learning_events
        WHERE DATE(timestamp) = ?
        """, (date,))
        
        total_events, lessons_learned = cursor.fetchone()
        
        conn.close()
        
        report = {
            "date": date,
            "total_events": total_events,
            "lessons_learned": lessons_learned,
            "optimizations_applied": 0
        }
        
        # Salva relatório
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT OR REPLACE INTO daily_reports
        (date, total_events, lessons_learned, report_json)
        VALUES (?, ?, ?, ?)
        """, (
            date,
            total_events,
            lessons_learned,
            json.dumps(report)
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"📊 Relatório diário gerado: {total_events} eventos, {lessons_learned} lições")
        
        return report
