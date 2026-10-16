#!/usr/bin/env python3
"""
Sandbox Executor - Execução segura de código Python gerado por IA

Baseado em: SafeRun (PyPI, 2025) e sandbox-executor (PyPI, 2025)

Uso:
    sandbox = SandboxExecutor()
    result = sandbox.execute(code, timeout=5, memory_limit_mb=128)
"""

import subprocess
import tempfile
import os
import resource
import signal
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
from loguru import logger


class SandboxExecutor:
    """Executa código Python em sandbox isolado"""
    
    # Módulos proibidos (perigosos)
    DANGEROUS_MODULES = {
        "os", "sys", "subprocess", "multiprocessing",
        "socket", "http", "urllib", "requests",
        "ctypes", "pickle", "marshal", "shelve",
        "importlib", "pkgutil", "inspect",
        "__import__", "eval", "exec", "compile",
        "open", "file", "input", "raw_input"
    }
    
    # Imports permitidos (seguros)
    SAFE_IMPORTS = {
        "math", "random", "datetime", "time",
        "collections", "itertools", "functools",
        "re", "json", "csv", "typing",
        "dataclasses", "pathlib", "io",
        "string", "textwrap", "unicodedata"
    }
    
    def __init__(
        self,
        timeout: int = 5,
        memory_limit_mb: int = 128,
        cpu_limit: int = 1,
        network_enabled: bool = False
    ):
        self.timeout = timeout
        self.memory_limit_mb = memory_limit_mb
        self.cpu_limit = cpu_limit
        self.network_enabled = network_enabled
        
        logger.info(f"🔒 SandboxExecutor inicializado (timeout={timeout}s, mem={memory_limit_mb}MB)")
    
    def execute(
        self,
        code: str,
        input_data: Optional[str] = None
    ) -> Dict[str, Any]:
        """Executa código em sandbox"""
        
        logger.info("🔒 Executando código em sandbox...")
        
        # 1. Validação AST (análise estática)
        is_safe, ast_errors = self._validate_ast(code)
        
        if not is_safe:
            logger.warning(f"⚠️  Código rejeitado na validação AST: {ast_errors}")
            return {
                "success": False,
                "error": "Código inseguro detectado",
                "details": ast_errors,
                "stdout": "",
                "stderr": "",
                "exit_code": -1
            }
        
        # 2. Cria diretório temporário isolado
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "sandbox_script.py"
            
            # Escreve script
            script_path.write_text(code, encoding="utf-8")
            
            # 3. Configura limites de recursos
            limits = {
                "RLIMIT_CPU": self.cpu_limit,
                "RLIMIT_AS": self.memory_limit_mb * 1024 * 1024,  # Memória virtual
                "RLIMIT_FSIZE": 10 * 1024 * 1024,  # Arquivos máx 10MB
                "RLIMIT_NOFILE": 64  # Máx 64 arquivos abertos
            }
            
            # 4. Prepara comando
            cmd = ["python3", str(script_path)]
            
            env = os.environ.copy()
            env["PYTHONPATH"] = tmpdir
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            
            # 5. Executa com isolamento
            try:
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    cwd=tmpdir,
                    preexec_fn=lambda: self._apply_limits(limits)
                )
                
                stdout, stderr = process.communicate(
                    input=input_data.encode() if input_data else None,
                    timeout=self.timeout
                )
                
                result = {
                    "success": process.returncode == 0,
                    "error": None,
                    "details": None,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "exit_code": process.returncode
                }
                
                logger.info(f"✅ Execução concluída: exit_code={process.returncode}")
                return result
            
            except subprocess.TimeoutExpired:
                process.kill()
                logger.error("⏰ Timeout na execução")
                return {
                    "success": False,
                    "error": "Timeout",
                    "details": f"Código excedeu {self.timeout} segundos",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -2
                }
            
            except Exception as e:
                logger.error(f"❌ Erro na execução: {e}")
                return {
                    "success": False,
                    "error": str(e),
                    "details": None,
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -3
                }
    
    def _apply_limits(self, limits: Dict[str, int]):
        """Aplica limites de recursos ao processo"""
        
        # Limita CPU
        if "RLIMIT_CPU" in limits:
            resource.setrlimit(resource.RLIMIT_CPU, (limits["RLIMIT_CPU"], limits["RLIMIT_CPU"]))
        
        # Limita memória
        if "RLIMIT_AS" in limits:
            resource.setrlimit(resource.RLIMIT_AS, (limits["RLIMIT_AS"], limits["RLIMIT_AS"]))
        
        # Limita tamanho de arquivos
        if "RLIMIT_FSIZE" in limits:
            resource.setrlimit(resource.RLIMIT_FSIZE, (limits["RLIMIT_FSIZE"], limits["RLIMIT_FSIZE"]))
        
        # Limita arquivos abertos
        if "RLIMIT_NOFILE" in limits:
            resource.setrlimit(resource.RLIMIT_NOFILE, (limits["RLIMIT_NOFILE"], limits["RLIMIT_NOFILE"]))
        
        # Bloqueia sinais perigosos
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)
    
    def _validate_ast(self, code: str) -> Tuple[bool, list]:
        """Valida código com AST (análise estática)"""
        
        import ast
        
        errors = []
        
        try:
            tree = ast.parse(code)
        
        except SyntaxError as e:
            errors.append(f"Erro de sintaxe: {e}")
            return False, errors
        
        # Verifica imports perigosos
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in self.DANGEROUS_MODULES:
                        errors.append(f"Import perigoso: {alias.name}")
            
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module in self.DANGEROUS_MODULES:
                    errors.append(f"ImportFrom perigoso: {node.module}")
            
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.DANGEROUS_MODULES:
                        errors.append(f"Chamada perigosa: {node.func.id}()")
        
        # Verifica chamadas eval/exec
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ["eval", "exec", "compile"]:
                        errors.append(f"Função proibida: {node.func.id}()")
        
        return len(errors) == 0, errors
    
    def execute_with_retry(
        self,
        code: str,
        max_retries: int = 3,
        input_data: Optional[str] = None
    ) -> Dict[str, Any]:
        """Executa código com retry automático"""
        
        for attempt in range(max_retries):
            result = self.execute(code, input_data)
            
            if result["success"]:
                return result
            
            # Se falhou por timeout, tenta aumentar limite
            if result["error"] == "Timeout" and attempt < max_retries - 1:
                logger.warning(f"⚠️  Timeout na tentativa {attempt+1}, aumentando para {self.timeout * 2}s")
                self.timeout *= 2
            
            # Se falhou por erro de segurança, não retry
            if result["error"] == "Código inseguro detectado":
                break
        
        return result
