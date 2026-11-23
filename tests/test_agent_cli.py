"""Contrato CLI do comando `yby agent` (offline; sem Ollama/rede)."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from src.main import cli

ROOT = Path(__file__).resolve().parents[1]
DEMO_SCRIPT = ROOT / "examples" / "agent_demo_script.json"


def test_agent_script_happy_path() -> None:
    result = CliRunner().invoke(
        cli,
        ["agent", "demo", "--script", str(DEMO_SCRIPT)],
    )
    assert result.exit_code == 0
    assert "status: completed" in result.output
    assert "Entregável mínimo validado" in result.output


def test_agent_script_json_flag() -> None:
    result = CliRunner().invoke(
        cli,
        ["agent", "demo", "--script", str(DEMO_SCRIPT), "--json"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["status"] == "completed"
    assert payload["final_answer"]["summary"] == "Entregável mínimo validado"
    assert payload["iterations"] >= 1


def test_agent_sem_modo() -> None:
    result = CliRunner().invoke(cli, ["agent", "sem-modo"])
    assert result.exit_code == 1
    assert "--script" in result.output
    assert "--local" in result.output


def test_agent_script_e_local_juntos() -> None:
    result = CliRunner().invoke(
        cli,
        ["agent", "conflito", "--script", str(DEMO_SCRIPT), "--local"],
    )
    assert result.exit_code == 1
    assert "Use apenas um de --script ou --local." in result.output


def test_agent_script_json_nao_array(tmp_path: Path) -> None:
    bad = tmp_path / "not-array.json"
    bad.write_text("{}\n", encoding="utf-8")
    result = CliRunner().invoke(
        cli,
        ["agent", "json-ruim", "--script", str(bad)],
    )
    assert result.exit_code == 1
    assert "O script deve ser um JSON array de passos." in result.output
