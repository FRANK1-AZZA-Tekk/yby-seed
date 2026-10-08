#!/usr/bin/env python3
"""
Metrics Dashboard - Dashboard de métricas do YBY SEED

Baseado em: AI Agent Evaluation Frameworks (2026)

Uso:
    dashboard = MetricsDashboard()
    dashboard.log_task_completion(task_id, success, time_seconds, cost_brl)
    dashboard.generate_report()
"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from pathlib import Path
from loguru import logger
import sqlite3


class MetricsDashboard:
    """Dashboard de métricas de avaliação"""
    
    def __init__(self, db_path: str = "/tmp/yby_metrics.db"):
        self.db_path = db_path
        self._init_db()
        logger.info(f"📊 MetricsDashboard inicializado (DB: {db_path})")
    
    def _init_db(self):
        """Inicializa banco de métricas"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela de execuções
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            task_id TEXT NOT NULL,
            success BOOLEAN NOT NULL,
            elapsed_time_seconds REAL NOT NULL,
            cost_brl REAL NOT NULL,
            human_override BOOLEAN DEFAULT FALSE,
            error_message TEXT
        )
        """)
        
        # Tabela de métricas diárias
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            total_tasks INTEGER NOT NULL,
            successful_tasks INTEGER NOT NULL,
            avg_time_seconds REAL NOT NULL,
            avg_cost_brl REAL NOT NULL,
            human_override_rate REAL NOT NULL,
            task_completion_rate REAL NOT NULL
        )
        """)
        
        conn.commit()
        conn.close()
    
    def log_task_completion(
        self,
        task_id: str,
        success: bool,
        elapsed_time_seconds: float,
        cost_brl: float,
        human_override: bool = False,
        error_message: str = None
    ):
        """Loga conclusão de tarefa"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT INTO task_executions
        (timestamp, task_id, success, elapsed_time_seconds, cost_brl, human_override, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            task_id,
            success,
            elapsed_time_seconds,
            cost_brl,
            human_override,
            error_message
        ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"📊 Tarefa {task_id} logada: success={success}, time={elapsed_time_seconds:.2f}s")
    
    def get_task_completion_rate(self, days: int = 7) -> float:
        """Retorna taxa de conclusão de tarefas (últimos N dias)"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
        SELECT COUNT(*), SUM(CASE WHEN success THEN 1 ELSE 0 END)
        FROM task_executions
        WHERE timestamp > ?
        """, (cutoff,))
        
        total, successful = cursor.fetchone()
        conn.close()
        
        if total == 0:
            return 0.0
        
        return successful / total
    
    def get_human_override_rate(self, days: int = 7) -> float:
        """Retorna taxa de override humano (últimos N dias)"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
        SELECT COUNT(*), SUM(CASE WHEN human_override THEN 1 ELSE 0 END)
        FROM task_executions
        WHERE timestamp > ?
        """, (cutoff,))
        
        total, overrides = cursor.fetchone()
        conn.close()
        
        if total == 0:
            return 0.0
        
        return overrides / total
    
    def get_avg_latency_p95(self, days: int = 7) -> float:
        """Retorna latência p95 (últimos N dias)"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
        SELECT elapsed_time_seconds
        FROM task_executions
        WHERE timestamp > ?
        ORDER BY elapsed_time_seconds DESC
        LIMIT 1 OFFSET (SELECT COUNT(*) * 95 / 100 FROM task_executions WHERE timestamp > ?)
        """, (cutoff, cutoff))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else 0.0
    
    def get_avg_cost_per_task(self, days: int = 7) -> float:
        """Retorna custo médio por tarefa (últimos N dias)"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
        SELECT AVG(cost_brl)
        FROM task_executions
        WHERE timestamp > ?
        """, (cutoff,))
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result[0] else 0.0
    
    def generate_report(self, days: int = 7) -> Dict[str, Any]:
        """Gera relatório de métricas"""
        
        logger.info(f"📊 Gerando relatório de métricas (últimos {days} dias)...")
        
        report = {
            "period_days": days,
            "generated_at": datetime.now().isoformat(),
            
            # Métricas principais
            "task_completion_rate": self.get_task_completion_rate(days),
            "human_override_rate": self.get_human_override_rate(days),
            "latency_p95_seconds": self.get_avg_latency_p95(days),
            "avg_cost_brl": self.get_avg_cost_per_task(days),
            
            # Alvos
            "targets": {
                "task_completion_rate": 0.90,
                "human_override_rate": 0.10,
                "latency_p95_seconds": 300,
                "avg_cost_brl": 0.50
            },
            
            # Status
            "status": {}
        }
        
        # Calcula status
        report["status"]["task_completion_rate"] = "✅" if report["task_completion_rate"] >= 0.90 else "⚠️"
        report["status"]["human_override_rate"] = "✅" if report["human_override_rate"] <= 0.10 else "⚠️"
        report["status"]["latency_p95_seconds"] = "✅" if report["latency_p95_seconds"] <= 300 else "⚠️"
        report["status"]["avg_cost_brl"] = "✅" if report["avg_cost_brl"] <= 0.50 else "⚠️"
        
        # Salva relatório diário
        self._save_daily_report(report)
        
        logger.info(f"✅ Relatório gerado: {report['task_completion_rate']*100:.1f}% completion, {report['human_override_rate']*100:.1f}% override")
        
        return report
    
    def _save_daily_report(self, report: Dict[str, Any]):
        """Salva relatório diário no DB"""
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        today = datetime.now().strftime("%Y-%m-%d")
        
        cursor.execute("""
        INSERT OR REPLACE INTO daily_metrics
        (date, total_tasks, successful_tasks, avg_time_seconds, avg_cost_brl, human_override_rate, task_completion_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            today,
            0,  # Será atualizado depois
            0,
            report["latency_p95_seconds"],
            report["avg_cost_brl"],
            report["human_override_rate"],
            report["task_completion_rate"]
        ))
        
        conn.commit()
        conn.close()
    
    def export_report_json(self, days: int = 7, filepath: str = "metrics_report.json") -> str:
        """Exporta relatório para JSON"""
        
        report = self.generate_report(days)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"📊 Relatório exportado: {filepath}")
        
        return filepath
