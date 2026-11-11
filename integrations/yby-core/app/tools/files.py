from pathlib import Path

from langchain_core.tools import tool


ALLOWED_ROOT = Path.home() / "yby"


def safe_path(relative_path: str) -> Path:
    path = (ALLOWED_ROOT / relative_path).resolve()

    if not path.is_relative_to(ALLOWED_ROOT):
        raise ValueError("Acesso fora da pasta permitida do YBY.")

    return path


@tool
def read_yby_file(relative_path: str) -> str:
    """Lê um arquivo dentro da pasta permitida do projeto YBY."""
    path = safe_path(relative_path)

    if not path.exists():
        return f"Arquivo não encontrado: {relative_path}"

    return path.read_text(encoding="utf-8")[:8000]


@tool
def write_yby_file(relative_path: str, content: str) -> str:
    """Escreve um arquivo dentro da pasta permitida do projeto YBY."""
    path = safe_path(relative_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return f"Arquivo salvo: {relative_path}"
