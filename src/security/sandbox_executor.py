#!/usr/bin/env python3
"""
Sandbox Executor - Execução segura de código Python gerado por IA

Baseado em: SafeRun (PyPI, 2025) e sandbox-executor (PyPI, 2025)

Uso:
    sandbox = SandboxExecutor()
    result = sandbox.execute(code, timeout=5, memory_limit_mb=128)
"""

import base64
import os
import resource
import signal
import subprocess
import textwrap
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from src.security.ast_guard import SAFE_IMPORTS


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
    
    SAFE_IMPORTS = set(SAFE_IMPORTS)
    
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
            script_path.write_text(self._wrap_for_runtime(code), encoding="utf-8")
            
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
        """Usa a mesma guarda AST do GovernanceAgent."""

        from src.security.ast_guard import validate_code_ast

        return validate_code_ast(code)

    def _wrap_for_runtime(self, user_code: str) -> str:
        """Encapsula o código com namespace e audit hook restritos."""

        payload = base64.b64encode(user_code.encode("utf-8")).decode("ascii")
        safe_modules = ", ".join(repr(name) for name in sorted(self.SAFE_IMPORTS))
        blocked_builtins = (
            "eval",
            "exec",
            "compile",
            "open",
            "input",
            "getattr",
            "setattr",
            "delattr",
            "globals",
            "locals",
            "vars",
            "dir",
            "help",
            "memoryview",
            "bytearray",
            "chr",
            "breakpoint",
        )
        blocked_builtins_repr = ", ".join(repr(n) for n in blocked_builtins)
        blocked_dunders = (
            "__builtins__",
            "__class__",
            "__subclasses__",
            "__globals__",
            "__locals__",
            "__code__",
            "__closure__",
            "__dict__",
            "__bases__",
            "__mro__",
        )
        blocked_dunders_repr = ", ".join(repr(n) for n in blocked_dunders)
        return textwrap.dedent(
            f"""
            import base64
            import sys

            _USER_CODE = base64.b64decode({payload!r}).decode("utf-8")
            _SAFE_MODULES = {{{safe_modules}}}
            _BLOCKED_BUILTINS = {{{blocked_builtins_repr}}}
            _BLOCKED_DUNDERS = {{{blocked_dunders_repr}}}

            def _blocked_builtin(name):
                raise RuntimeError(f"builtin bloqueado: {{name}}")

            def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
                root = name.partition(".")[0]
                if root not in _SAFE_MODULES:
                    raise ImportError(f"módulo bloqueado: {{root}}")
                return __import__(name, globals, locals, fromlist, level)

            def _audit_hook(event, args):
                if event in ("input", "ctypes"):
                    raise RuntimeError(f"audit bloqueado: {{event}}")
                if event == "object.__getattribute__":
                    attr = args[1]
                    if attr in _BLOCKED_DUNDERS or (
                        isinstance(attr, str) and attr.startswith("__") and attr.endswith("__")
                    ):
                        raise RuntimeError(f"atributo bloqueado: {{attr}}")

            sys.addaudithook(_audit_hook)

            _SAFE_BUILTINS = {{
                "None": None,
                "True": True,
                "False": False,
                "print": print,
                "abs": abs,
                "all": all,
                "any": any,
                "bin": bin,
                "bool": bool,
                "dict": dict,
                "enumerate": enumerate,
                "float": float,
                "int": int,
                "len": len,
                "list": list,
                "max": max,
                "min": min,
                "range": range,
                "repr": repr,
                "reversed": reversed,
                "round": round,
                "set": set,
                "sorted": sorted,
                "str": str,
                "sum": sum,
                "tuple": tuple,
                "zip": zip,
                "isinstance": isinstance,
                "issubclass": issubclass,
                "__import__": _safe_import,
            }}
            for _name in _BLOCKED_BUILTINS:
                _SAFE_BUILTINS[_name] = lambda *a, _n=_name, **k: _blocked_builtin(_n)

            def _run_user():
                namespace = {{"__name__": "__main__", "__builtins__": _SAFE_BUILTINS}}
                exec(_USER_CODE, namespace, namespace)

            if __name__ == "__main__":
                _run_user()
            """
        ).lstrip()
    
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
            
            if result["error"] == "Timeout" and attempt < max_retries - 1:
                logger.warning(f"Timeout na tentativa {attempt + 1}")
            
            # Se falhou por erro de segurança, não retry
            if result["error"] == "Código inseguro detectado":
                break
        
        return result
