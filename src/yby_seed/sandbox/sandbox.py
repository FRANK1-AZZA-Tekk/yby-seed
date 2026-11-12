"""Executor efêmero via Docker SDK (rede off, 512MB, 30s) com lint multi-domínio."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.yby_seed.config import Settings, get_settings
from src.yby_seed.runtime import resources
from src.yby_seed.sandbox.hardware_linter import analyze_hardware
from src.yby_seed.sandbox.runners import select_runner

logger = logging.getLogger(__name__)
MAX_LOG_BYTES = 65_536
PREFERRED_SANDBOX_IMAGE = "yby-sandbox:latest"
FALLBACK_SANDBOX_IMAGE = "python:3.12-slim"


def resolve_sandbox_python_image(settings: Settings) -> str:
    """Prefere imagem quente yby-sandbox:latest se existir localmente."""
    configured = settings.sandbox_python_image
    if shutil.which("docker") is None:
        return configured or FALLBACK_SANDBOX_IMAGE
    try:
        client = resources.get_docker_client_sync()
    except Exception:  # noqa: BLE001
        return configured or FALLBACK_SANDBOX_IMAGE
    for image in (PREFERRED_SANDBOX_IMAGE, configured, FALLBACK_SANDBOX_IMAGE):
        try:
            client.images.get(image)
            return image
        except Exception:  # noqa: BLE001
            continue
    return FALLBACK_SANDBOX_IMAGE


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


def _run_docker(
    cmd_image: str, shell_cmd: str, work: Path, settings: Settings
) -> tuple[bool, str, str]:
    try:
        from docker.errors import DockerException
    except ImportError:
        return False, "", "pacote docker não instalado"

    try:
        client = resources.get_docker_client_sync()
    except DockerException as exc:
        return False, "", f"falha ao conectar ao Docker: {exc}"

    container = None
    try:
        container = client.containers.create(
            image=cmd_image,
            command=["bash", "-lc", shell_cmd],
            volumes={str(work): {"bind": "/work", "mode": "rw"}},
            network_mode="none",
            mem_limit=f"{settings.sandbox_memory_mb}m",
            nano_cpus=1_000_000_000,
            pids_limit=64,
            working_dir="/work",
        )
        container.start()
        result = container.wait(timeout=settings.sandbox_timeout_sec)
        stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
        if len(stdout) > MAX_LOG_BYTES:
            stdout = stdout[:MAX_LOG_BYTES] + "\n...[stdout truncado]"
        if len(stderr) > MAX_LOG_BYTES:
            stderr = stderr[:MAX_LOG_BYTES] + "\n...[stderr truncado]"
        ok = result.get("StatusCode", 1) == 0
        return ok, stdout, stderr
    except Exception as exc:  # noqa: BLE001
        return False, "", str(exc)
    finally:
        if container is not None:
            try:
                container.remove(force=True)
            except Exception as exc:  # noqa: BLE001
                logger.warning("falha ao remover container sandbox: %s", exc)


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
        image = command.image
        if language == "python":
            image = resolve_sandbox_python_image(settings)
        ok, stdout, stderr = _run_docker(image, command.shell_cmd, work, settings)
        report["docker"] = {"ok": ok}
        report["pinning_modbus_approved"] = report.get("hardware", {}).get("pinning_approved", True)

        if ok and embedded_or_industrial:
            report["validation_summary"] = (
                "Pinagem/Modbus aprovados pelo hardware_linter; sandbox Docker OK."
            )
            stdout = (stdout or "") + "\n" + json.dumps(report, ensure_ascii=False)

        return ValidationResult(success=ok, stdout=stdout, stderr=stderr, report=report)
