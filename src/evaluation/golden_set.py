#!/usr/bin/env python3
"""
Golden Set - Tarefas de benchmark para avaliar evolução do sistema

Baseado em: SWE-bench Verified, GAIA, AgentBench (2025-2026)

Uso:
    golden = GoldenSet()
    score = golden.evaluate(agent_function)
"""

from typing import Dict, Any, List, Callable
from dataclasses import dataclass
from loguru import logger
import json


@dataclass
class Task:
    """Tarefa de benchmark"""
    
    id: str
    description: str
    expected_output: str
    difficulty: str  # "fácil", "médio", "difícil"
    category: str  # "backup", "api", "data_processing", etc.
    timeout_seconds: int = 60
    max_cost_brl: float = 0.50


class GoldenSet:
    """Conjunto de tarefas para avaliar o YBY SEED"""
    
    def __init__(self):
        self.tasks = self._load_tasks()
        logger.info(f"📊 GoldenSet carregado com {len(self.tasks)} tarefas")
    
    def _load_tasks(self) -> List[Task]:
        """Carrega tarefas de benchmark"""
        
        return [
            # Tarefas Fáceis (5)
            Task(
                id="easy_01",
                description="Criar script que lista arquivos de uma pasta",
                expected_output="Script com os.listdir() e tratamento de FileNotFoundError",
                difficulty="fácil",
                category="file_operations",
                timeout_seconds=30,
                max_cost_brl=0.10
            ),
            Task(
                id="easy_02",
                description="Criar script que conta palavras em um texto",
                expected_output="Script com split() e Counter",
                difficulty="fácil",
                category="data_processing",
                timeout_seconds=30,
                max_cost_brl=0.10
            ),
            Task(
                id="easy_03",
                description="Criar script que faz backup de um arquivo",
                expected_output="Script com shutil.copy e timestamp",
                difficulty="fácil",
                category="backup",
                timeout_seconds=30,
                max_cost_brl=0.10
            ),
            Task(
                id="easy_04",
                description="Criar script que envia email simples",
                expected_output="Script com smtplib e tratamento de erro",
                difficulty="fácil",
                category="notification",
                timeout_seconds=30,
                max_cost_brl=0.10
            ),
            Task(
                id="easy_05",
                description="Criar script que lê JSON e extrai campo específico",
                expected_output="Script com json.load e acesso a dict",
                difficulty="fácil",
                category="data_processing",
                timeout_seconds=30,
                max_cost_brl=0.10
            ),
            
            # Tarefas Médias (5)
            Task(
                id="medium_01",
                description="Criar script que monitora pasta e notifica novos arquivos",
                expected_output="Script com watchdog e notificação",
                difficulty="médio",
                category="monitoring",
                timeout_seconds=60,
                max_cost_brl=0.30
            ),
            Task(
                id="medium_02",
                description="Criar script que baixa dados de API e salva em CSV",
                expected_output="Script com requests e csv.writer",
                difficulty="médio",
                category="api",
                timeout_seconds=60,
                max_cost_brl=0.30
            ),
            Task(
                id="medium_03",
                description="Criar script que compacta PDFs antigos em ZIP",
                expected_output="Script com zipfile e filtro por data",
                difficulty="médio",
                category="backup",
                timeout_seconds=60,
                max_cost_brl=0.30
            ),
            Task(
                id="medium_04",
                description="Criar script que agenda tarefa para rodar diariamente",
                expected_output="Script com schedule ou cron",
                difficulty="médio",
                category="automation",
                timeout_seconds=60,
                max_cost_brl=0.30
            ),
            Task(
                id="medium_05",
                description="Criar script que valida CPF/CNPJ",
                expected_output="Script com algoritmo de validação",
                difficulty="médio",
                category="data_validation",
                timeout_seconds=60,
                max_cost_brl=0.30
            ),
            
            # Tarefas Difíceis (5)
            Task(
                id="hard_01",
                description="Criar sistema de backup automático com notificação e rotação",
                expected_output="Sistema completo com agendamento, backup, notificação e limpeza de antigos",
                difficulty="difícil",
                category="backup",
                timeout_seconds=120,
                max_cost_brl=0.50
            ),
            Task(
                id="hard_02",
                description="Criar integração completa com API do Telegram (bot)",
                expected_output="Bot que responde comandos e salva dados",
                difficulty="difícil",
                category="api",
                timeout_seconds=120,
                max_cost_brl=0.50
            ),
            Task(
                id="hard_03",
                description="Criar dashboard de métricas com dados em tempo real",
                expected_output="Dashboard com atualização automática",
                difficulty="difícil",
                category="visualization",
                timeout_seconds=120,
                max_cost_brl=0.50
            ),
            Task(
                id="hard_04",
                description="Criar pipeline de ETL simples (extrair, transformar, carregar)",
                expected_output="Pipeline completo com tratamento de erros",
                difficulty="difícil",
                category="data_processing",
                timeout_seconds=120,
                max_cost_brl=0.50
            ),
            Task(
                id="hard_05",
                description="Criar sistema de autenticação simples com JWT",
                expected_output="Sistema com login, registro e validação de token",
                difficulty="difícil",
                category="security",
                timeout_seconds=120,
                max_cost_brl=0.50
            )
        ]
    
    def evaluate(
        self,
        agent_function: Callable[[str], str],
        task_id: str
    ) -> Dict[str, Any]:
        """Avalia agente em uma tarefa específica"""
        
        task = next((t for t in self.tasks if t.id == task_id), None)
        
        if not task:
            return {
                "success": False,
                "error": f"Tarefa {task_id} não encontrada"
            }
        
        logger.info(f"📊 Avaliando tarefa {task_id}: {task.description[:50]}...")
        
        import time
        start_time = time.time()
        
        try:
            # Executa agente
            generated_code = agent_function(task.description)
            
            # Avalia resultado
            evaluation = self._evaluate_output(generated_code, task)
            
            elapsed_time = time.time() - start_time
            
            return {
                "success": evaluation["success"],
                "task_id": task_id,
                "task_description": task.description,
                "generated_code_length": len(generated_code),
                "evaluation": evaluation,
                "elapsed_time_seconds": elapsed_time,
                "within_timeout": elapsed_time <= task.timeout_seconds,
                "within_budget": evaluation.get("estimated_cost_brl", 0) <= task.max_cost_brl
            }
        
        except Exception as e:
            logger.error(f"❌ Erro na avaliação: {e}")
            
            return {
                "success": False,
                "task_id": task_id,
                "error": str(e)
            }
    
    def _evaluate_output(
        self,
        generated_code: str,
        task: Task
    ) -> Dict[str, Any]:
        """Avalia código gerado em relação ao esperado"""
        
        # Critérios de avaliação
        criteria = {
            "syntax_valid": self._check_syntax(generated_code),
            "has_required_imports": self._check_imports(generated_code, task),
            "has_error_handling": self._check_error_handling(generated_code),
            "matches_expected_output": self._check_expected_output(generated_code, task),
            "is_executable": self._check_executable(generated_code)
        }
        
        # Calcula score
        score = sum(criteria.values()) / len(criteria)
        
        return {
            "success": score >= 0.8,
            "score": score,
            "criteria": criteria,
            "estimated_cost_brl": len(generated_code) / 1000 * 0.01  # Estimativa simples
        }
    
    def _check_syntax(self, code: str) -> bool:
        """Verifica sintaxe Python"""
        
        import ast
        
        try:
            ast.parse(code)
            return True
        
        except SyntaxError:
            return False
    
    def _check_imports(self, code: str, task: Task) -> bool:
        """Verifica se tem imports necessários"""
        
        # Mapeia categoria para imports esperados
        expected_imports = {
            "file_operations": ["os", "pathlib"],
            "data_processing": ["json", "csv"],
            "backup": ["shutil", "zipfile"],
            "notification": ["smtplib", "requests"],
            "api": ["requests"],
            "monitoring": ["watchdog"],
            "automation": ["schedule"],
            "data_validation": ["re"],
            "visualization": ["matplotlib"],
            "security": ["jwt", "hashlib"]
        }
        
        imports_for_category = expected_imports.get(task.category, [])
        
        return any(imp in code for imp in imports_for_category)
    
    def _check_error_handling(self, code: str) -> bool:
        """Verifica se tem tratamento de erros"""
        
        error_patterns = [
            "try:",
            "except",
            "if __name__",
            "raise"
        ]
        
        return any(pattern in code for pattern in error_patterns)
    
    def _check_expected_output(self, code: str, task: Task) -> bool:
        """Verifica se código corresponde ao esperado"""
        
        # Verifica palavras-chave do expected_output
        keywords = task.expected_output.lower().split()
        
        code_lower = code.lower()
        
        matches = sum(1 for kw in keywords if kw in code_lower)
        
        return matches >= len(keywords) * 0.5
    
    def _check_executable(self, code: str) -> bool:
        """Verifica se código é executável"""
        
        # Verifica estrutura mínima
        has_main = "if __name__" in code or "def main" in code
        has_entry_point = has_main or code.strip().startswith("import")
        
        return has_entry_point
    
    def run_full_benchmark(self, agent_function: Callable[[str], str]) -> Dict[str, Any]:
        """Rodar benchmark completo em todas as tarefas"""
        
        logger.info("📊 Iniciando benchmark completo...")
        
        results = []
        
        for task in self.tasks:
            result = self.evaluate(agent_function, task.id)
            results.append(result)
        
        # Calcula métricas agregadas
        total_tasks = len(results)
        successful_tasks = sum(1 for r in results if r.get("success", False))
        
        task_completion_rate = successful_tasks / total_tasks if total_tasks > 0 else 0
        
        avg_time = sum(r.get("elapsed_time_seconds", 0) for r in results) / total_tasks
        
        return {
            "total_tasks": total_tasks,
            "successful_tasks": successful_tasks,
            "task_completion_rate": task_completion_rate,
            "average_time_seconds": avg_time,
            "results_by_difficulty": self._group_by_difficulty(results),
            "results_by_category": self._group_by_category(results),
            "detailed_results": results
        }
    
    def _group_by_difficulty(self, results: List[Dict]) -> Dict[str, Any]:
        """Agrupa resultados por dificuldade"""
        
        grouped = {}
        
        for result in results:
            task = next((t for t in self.tasks if t.id == result["task_id"]), None)
            
            if task:
                difficulty = task.difficulty
                
                if difficulty not in grouped:
                    grouped[difficulty] = {"total": 0, "successful": 0}
                
                grouped[difficulty]["total"] += 1
                
                if result.get("success", False):
                    grouped[difficulty]["successful"] += 1
        
        # Calcula taxas
        for difficulty in grouped:
            total = grouped[difficulty]["total"]
            successful = grouped[difficulty]["successful"]
            grouped[difficulty]["rate"] = successful / total if total > 0 else 0
        
        return grouped
    
    def _group_by_category(self, results: List[Dict]) -> Dict[str, Any]:
        """Agrupa resultados por categoria"""
        
        grouped = {}
        
        for result in results:
            task = next((t for t in self.tasks if t.id == result["task_id"]), None)
            
            if task:
                category = task.category
                
                if category not in grouped:
                    grouped[category] = {"total": 0, "successful": 0}
                
                grouped[category]["total"] += 1
                
                if result.get("success", False):
                    grouped[category]["successful"] += 1
        
        # Calcula taxas
        for category in grouped:
            total = grouped[category]["total"]
            successful = grouped[category]["successful"]
            grouped[category]["rate"] = successful / total if total > 0 else 0
        
        return grouped
