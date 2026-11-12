"""Executor efêmero via Docker SDK (rede off, 512MB, 30s) com lint multi-domínio."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.yby_seed.config import Settings, get_settings
from src.yby_seed.sandbox.hardware_linter import analyze_hardware
from src.yby_seed.sandbox.runners import select_runner

DOMAIN_LANGUAGE: dict[str, str] = {
    "python_fastapi": "python",
    "esp_idf": "cpp_embedded",
    "lvgl_v9": "cpp_embedded",
    "modbus_rtu": "python",
}


@dataclass
class ValidationResult:
    success: bool
    stdout: str
    stderr: str
    report: dict[str, Any] = field(default_factory=dict)

    def as_tuple(self) -> tuple[bool, str, str]:
        return self.success, self.stdout, self.stderr


class SandboxError(RuntimeError):
    pass


def _run_docker(cmd_image: str, shell_cmd: str, work: Path, settings: Settings) -> tuple[bool, str, str]:
    try:
        from docker.errors import DockerException

        import docker
    except ImportError:
        return False, "", "pacote docker não instalado"

    try:
        client = docker.from_env()
    except DockerException as exc:
        return False, "", f"falha ao conectar ao Docker: {exc}"

    container = None
    try:
        container = client.containers.create(
            image=cmd_image,
            command=["bash", "-lc", shell_cmd],
            volumes={str(work): {"bind": "/work", "mode": "rw"}},
            network_mode="none",
            mem_limit=settings.sandbox_memory_mb * 1024 * 1024,
            working_dir="/work",
        )
        container.start()
        result = container.wait(timeout=settings.sandbox_timeout_sec)
        stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
        ok = result.get("StatusCode", 1) == 0
        return ok, stdout, stderr
    except Exception as exc:  # noqa: BLE001
        return False, "", str(exc)
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception:  # noqa: BLE001, S110
                pass


def execute_validated(
    *,
    language: str,
    code: str,
    filename: str,
    tests: str | None = None,
    settings: Settings | None = None,
    domain: str | None = None,
    board: str | None = None,
) -> ValidationResult:
    """Validação determinística multi-domínio."""
    settings = settings or get_settings()
    report: dict[str, Any] = {"domain": domain, "language": language, "runner": None}

    embedded_or_industrial = domain in {"esp_idf", "lvgl_v9", "modbus_rtu"}
    if embedded_or_industrial or language == "cpp_embedded":
        hw = analyze_hardware(code, domain=domain or "esp_idf", board=board)
        report["hardware"] = hw.to_dict()
        if not hw.gpio_ok or not hw.modbus_ok:
            issues = hw.gpio_issues + hw.modbus_issues
            return ValidationResult(
                success=False,
                stdout="",
                stderr="hardware_linter: " + "; ".join(issues),
                report=report,
            )

    if shutil.which("docker") is None:
        return ValidationResult(False, "", "docker não encontrado no PATH", report)

    try:
        runner = select_runner(language, settings)
    except ValueError as exc:
        return ValidationResult(False, "", str(exc), report)

    report["runner"] = runner.__class__.__name__

    with tempfile.TemporaryDirectory(prefix="yby-sandbox-") as tmp:
        work = Path(tmp)
        command = runner.build(work, code, filename, tests)
        ok, stdout, stderr = _run_docker(command.image, command.shell_cmd, work, settings)
        report["docker"] = {"ok": ok}
        report["pinning_modbus_approved"] = report.get("hardware", {}).get("pinning_approved", True)

        if ok and embedded_or_industrial:
            report["validation_summary"] = (
                "Pinagem/Modbus aprovados pelo hardware_linter; sandbox Docker OK."
            )
            stdout = (stdout or "") + "\n" + json.dumps(report, ensure_ascii=False)

        return ValidationResult(success=ok, stdout=stdout, stderr=stderr, report=report)


def execute_validated_legacy(
    *,
    language: str,
    code: str,
    filename: str,
    tests: str | None = None,
    settings: Settings | None = None,
    domain: str | None = None,
) -> tuple[bool, str, str]:
    """Compatibilidade com chamadas antigas (tupla)."""
    result = execute_validated(
        language=language,
        code=code,
        filename=filename,
        tests=tests,
        settings=settings,
        domain=domain,
    )
    return result.as_tuple()
