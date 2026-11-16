"""Templates mínimos Python/CLI. Sem framework web até evidência/OK."""

from __future__ import annotations

from src.engine.secret_gate import find_secret


def python_cli_files(*, name: str, objective: str) -> dict[str, str]:
    """Árvore relativa → conteúdo. Sem segredos."""

    safe = _safe_name(name)
    readme = f"""# {safe}

{objective}

Stack: Python CLI local (sem framework web neste scaffold).

## Uso

```bash
python -m {safe} --help
python -m pytest
```

Não rode `pip install` automático pelo YBY — instale deps localmente se precisar.
"""
    main_py = f'''"""CLI mínima gerada pelo YBY (proposta até aprovação)."""

from __future__ import annotations


def main() -> None:
    print("{safe}: ok")


if __name__ == "__main__":
    main()
'''
    init_py = '"""Pacote gerado."""\n'
    test_py = f'''"""Teste mínimo do scaffold {safe}."""

from {safe} import main


def test_main_runs(capsys) -> None:
    main.main()
    assert "{safe}: ok" in capsys.readouterr().out
'''
    pyproject = f"""[project]
name = "{safe}"
version = "0.1.0"
description = "{_one_line(objective)}"
requires-python = ">=3.11"

[tool.pytest.ini_options]
pythonpath = ["."]
"""
    files = {
        "README.md": readme,
        "pyproject.toml": pyproject,
        f"{safe}/__init__.py": init_py,
        f"{safe}/__main__.py": "from .main import main\n\nif __name__ == '__main__':\n    main()\n",
        f"{safe}/main.py": main_py,
        f"tests/test_{safe}.py": test_py,
    }
    for path, body in files.items():
        if find_secret(body) is not None:
            raise ValueError(f"template produziu segredo em {path}")
    return files


def _safe_name(name: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name.strip())
    cleaned = cleaned.strip("_").casefold() or "yby_app"
    if cleaned[0].isdigit():
        cleaned = f"app_{cleaned}"
    return cleaned[:40]


def _one_line(text: str) -> str:
    return " ".join(text.split()).replace('"', "'")[:120]
