#!/usr/bin/env python3
"""
Sandbox Executor — execução restrita de código Python gerado por IA.

Camada 1: AST allowlist (src.security.ast_guard)
Camada 2: processo isolado com env mínimo, python -I, cwd temporário e limites.

Referências: sandboxes em duas camadas e advisories de bypass AST (2025–2026).
"""

from __future__ import annotations

import os
import resource
import signal
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from loguru import logger

from src.security.ast_guard import SAFE_IMPORTS, validate_code_ast


class SandboxExecutor:
    """Executa código Python em sandbox isolado."""

    SAFE_IMPORTS = SAFE_IMPORTS

    def __init__(
        self,
        timeout: int = 5,
        memory_limit_mb: int = 128,
        cpu_limit: int = 1,
        network_enabled: bool = False,
    ):
        self.timeout = timeout
        self.memory_limit_mb = memory_limit_mb
        self.cpu_limit = cpu_limit
        # Documentado: ainda sem netns; False implica env sem proxies e sem rede configurada.
        self.network_enabled = network_enabled
        if network_enabled:
            logger.warning(
                "network_enabled=True ainda não aplica namespace de rede; "
                "trate como não isolado de rede."
            )

        logger.info(
            f"🔒 SandboxExecutor (timeout={timeout}s, mem={memory_limit_mb}MB)"
        )

    def _scrubbed_env(self, tmpdir: str) -> dict[str, str]:
        """Ambiente mínimo — sem secrets/PATH do host completo."""
        path = os.environ.get("PATH", "/usr/bin:/bin")
        env = {
            "PATH": path,
            "HOME": tmpdir,
            "TMPDIR": tmpdir,
            "LANG": os.environ.get("LANG", "C.UTF-8"),
            "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
        if self.network_enabled:
            for key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
                if key in os.environ:
                    env[key] = os.environ[key]
        return env

    def execute(
        self,
        code: str,
        input_data: str | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Executa código em sandbox."""
        run_timeout = self.timeout if timeout is None else timeout
        logger.info("🔒 Executando código em sandbox...")

        is_safe, ast_errors = self._validate_ast(code)
        if not is_safe:
            logger.warning(f"⚠️  Código rejeitado na validação AST: {ast_errors}")
            return {
                "success": False,
                "error": "Código inseguro detectado",
                "details": ast_errors,
                "stdout": "",
                "stderr": "",
                "exit_code": -1,
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "sandbox_script.py"
            script_path.write_text(code, encoding="utf-8")

            limits = {
                "RLIMIT_CPU": self.cpu_limit,
                "RLIMIT_AS": self.memory_limit_mb * 1024 * 1024,
                "RLIMIT_FSIZE": 10 * 1024 * 1024,
                "RLIMIT_NOFILE": 64,
            }

            # -I: modo isolado (ignora PYTHONPATH / user site)
            cmd = ["python3", "-I", str(script_path)]
            env = self._scrubbed_env(tmpdir)

            process: subprocess.Popen[bytes] | None = None
            try:
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=env,
                    cwd=tmpdir,
                    preexec_fn=lambda: self._apply_limits(limits),
                )

                stdout, stderr = process.communicate(
                    input=input_data.encode() if input_data else None,
                    timeout=run_timeout,
                )

                result = {
                    "success": process.returncode == 0,
                    "error": None,
                    "details": None,
                    "stdout": stdout.decode("utf-8", errors="replace"),
                    "stderr": stderr.decode("utf-8", errors="replace"),
                    "exit_code": process.returncode,
                }
                logger.info(f"✅ Execução concluída: exit_code={process.returncode}")
                return result

            except subprocess.TimeoutExpired:
                if process is not None:
                    process.kill()
                    process.wait(timeout=2)
                logger.error("⏰ Timeout na execução")
                return {
                    "success": False,
                    "error": "Timeout",
                    "details": f"Código excedeu {run_timeout} segundos",
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -2,
                }

            except Exception as exc:
                logger.error(f"❌ Erro na execução: {exc}")
                return {
                    "success": False,
                    "error": str(exc),
                    "details": None,
                    "stdout": "",
                    "stderr": "",
                    "exit_code": -3,
                }

    def _apply_limits(self, limits: dict[str, int]) -> None:
        if "RLIMIT_CPU" in limits:
            resource.setrlimit(
                resource.RLIMIT_CPU, (limits["RLIMIT_CPU"], limits["RLIMIT_CPU"])
            )
        if "RLIMIT_AS" in limits:
            resource.setrlimit(
                resource.RLIMIT_AS, (limits["RLIMIT_AS"], limits["RLIMIT_AS"])
            )
        if "RLIMIT_FSIZE" in limits:
            resource.setrlimit(
                resource.RLIMIT_FSIZE, (limits["RLIMIT_FSIZE"], limits["RLIMIT_FSIZE"])
            )
        if "RLIMIT_NOFILE" in limits:
            resource.setrlimit(
                resource.RLIMIT_NOFILE,
                (limits["RLIMIT_NOFILE"], limits["RLIMIT_NOFILE"]),
            )
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)

    def _validate_ast(self, code: str) -> tuple[bool, list]:
        return validate_code_ast(code)

    def execute_with_retry(
        self,
        code: str,
        max_retries: int = 3,
        input_data: str | None = None,
    ) -> dict[str, Any]:
        """Executa com retry sem mutar self.timeout."""
        timeout = self.timeout
        result: dict[str, Any] = {
            "success": False,
            "error": "Sem tentativas",
            "details": None,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
        }

        for attempt in range(max_retries):
            result = self.execute(code, input_data, timeout=timeout)

            if result["success"]:
                return result

            if result["error"] == "Código inseguro detectado":
                break

            if result["error"] == "Timeout" and attempt < max_retries - 1:
                timeout = timeout * 2
                logger.warning(
                    f"⚠️  Timeout na tentativa {attempt + 1}, próximo timeout={timeout}s"
                )

        return result
