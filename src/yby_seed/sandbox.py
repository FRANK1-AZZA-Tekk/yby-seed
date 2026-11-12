"""Executor efêmero via Docker SDK (rede desligada, 512MB, 30s)."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from src.yby_seed.config import Settings, get_settings


class SandboxError(RuntimeError):
    pass


def _default_python_tests() -> str:
    return (
        "def test_smoke():\n"
        "    assert True\n"
    )


def execute_validated(
    *,
    language: str,
    code: str,
    filename: str,
    tests: str | None = None,
    settings: Settings | None = None,
) -> tuple[bool, str, str]:
    """Executa validação no container e retorna (success, stdout, stderr)."""
    settings = settings or get_settings()
    if shutil.which("docker") is None:
        return False, "", "docker não encontrado no PATH"

    try:
        from docker.errors import DockerException

        import docker
    except ImportError:
        return False, "", "pacote docker não instalado"

    client: docker.DockerClient
    try:
        client = docker.from_env()
    except DockerException as exc:
        return False, "", f"falha ao conectar ao Docker: {exc}"

    image = (
        settings.sandbox_python_image
        if language == "python"
        else settings.sandbox_cpp_image
    )

    with tempfile.TemporaryDirectory(prefix="yby-sandbox-") as tmp:
        work = Path(tmp)
        target = work / (filename if filename else "main.py")
        target.write_text(code, encoding="utf-8")

        if language == "python":
            test_path = work / "test_generated.py"
            test_path.write_text(tests or _default_python_tests(), encoding="utf-8")
            shell_cmd = "ruff check . && pytest -q"
        elif language == "cpp_embedded":
            cpp_name = target.name if target.suffix == ".cpp" else "firmware.cpp"
            if target.name != cpp_name:
                target.rename(work / cpp_name)
            shell_cmd = (
                f"g++ -std=c++17 -fsyntax-only -Werror -c /work/{cpp_name}"
            )
        else:
            return False, "", f"linguagem não suportada: {language}"

        container = None
        try:
            container = client.containers.create(
                image=image,
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
            code_ok = result.get("StatusCode", 1) == 0
            return code_ok, stdout, stderr
        except Exception as exc:  # noqa: BLE001
            return False, "", str(exc)
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:  # noqa: BLE001, S110
                    pass
