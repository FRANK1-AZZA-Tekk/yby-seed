"""Contrato da árvore Claude Code: Sonnet + Haiku só-leitura + Opus consultor."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / ".claude" / "settings.json"
AGENTS_DIR = ROOT / ".claude" / "agents"
CLAUDE_MD = ROOT / "CLAUDE.md"
FORBIDDEN_TOOLS = frozenset({"Edit", "Write", "Bash", "Agent"})
EXPECTED_AGENTS = ("search", "grep", "docs")


def _frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n", text, flags=re.DOTALL)
    assert match, f"{path.name} precisa de frontmatter YAML"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def _tool_names(tools_field: str) -> set[str]:
    return {part.strip() for part in tools_field.split(",") if part.strip()}


def test_settings_sonnet_com_advisor_opus() -> None:
    data = json.loads(SETTINGS.read_text(encoding="utf-8"))
    assert data == {"model": "sonnet", "advisorModel": "opus"}
    assert set(data) == {"model", "advisorModel"}


def test_subagentes_haiku_somente_leitura() -> None:
    for name in EXPECTED_AGENTS:
        path = AGENTS_DIR / f"{name}.md"
        assert path.is_file(), f"falta {path.relative_to(ROOT)}"
        fields = _frontmatter(path)
        assert fields["name"] == name
        assert fields["model"] == "haiku"
        assert fields.get("effort") == "low"
        assert fields.get("maxTurns") == "4"
        assert fields.get("omitClaudeMd") == "true"
        tools = _tool_names(fields["tools"])
        assert tools, f"{name} precisa listar tools"
        assert tools.isdisjoint(FORBIDDEN_TOOLS), f"{name} não pode ter {FORBIDDEN_TOOLS & tools}"
        assert "description" in fields and fields["description"]


def test_claude_md_portoes_e_sem_jev_router() -> None:
    text = CLAUDE_MD.read_text(encoding="utf-8").casefold()
    assert "antes de travar o plano" in text
    assert "mesmo erro" in text
    assert "declarar concluído" in text or "declarar concluido" in text
    assert "make doctor" in text
    assert "make lint" in text
    assert "make test" in text
    assert "jev-router" in text
    assert "não instale" in text or "nao instale" in text
    assert "decide_route" in text
    assert "src/safety" in text
