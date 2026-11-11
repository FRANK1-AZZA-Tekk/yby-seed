import subprocess
from pathlib import Path

from langchain_core.tools import tool


ALLOWED_ROOT = Path.home() / "yby"


@tool
def platformio_build(project_path: str) -> str:
    """Compila um projeto PlatformIO dentro da pasta permitida do YBY."""
    project = (ALLOWED_ROOT / project_path).resolve()

    if not project.is_relative_to(ALLOWED_ROOT):
        return "Erro: caminho fora da pasta permitida."

    if not (project / "platformio.ini").exists():
        return "Erro: projeto não possui platformio.ini."

    result = subprocess.run(
        ["pio", "run", "--project-dir", str(project)],
        capture_output=True,
        text=True,
        timeout=300,
    )

    output = result.stdout[-4000:] + result.stderr[-2000:]

    return (
        f"Build finalizado com código {result.returncode}.\n\n"
        f"{output}"
    )
