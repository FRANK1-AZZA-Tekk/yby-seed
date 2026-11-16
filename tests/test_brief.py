"""Lote 14: YBY-BRIEF — entrevista, retomada, proposta; sem código."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from src.brief.interview import (
    BriefError,
    answer_field,
    missing_fields,
    next_questions,
    start_brief,
    try_propose,
)
from src.brief.store import BriefStore
from src.main import cli


def test_ideia_vaga_gera_perguntas() -> None:
    brief, questions = start_brief("app")
    assert brief.status == "draft"
    assert questions
    assert missing_fields(brief)
    assert "objetivo" in questions[0].casefold() or "concreto" in questions[0].casefold()


def test_brief_incompleto_nao_gera_proposta() -> None:
    brief, _ = start_brief("agenda local para estudar português")
    try:
        try_propose(brief)
        raise AssertionError("deveria falhar")
    except BriefError as exc:
        assert "incompleto" in str(exc)
        assert "plano não gerado" in str(exc)
    assert brief.proposal is None
    assert brief.status == "draft"


def _fill_all(brief) -> None:
    answers = {
        "objective": "lembrar vocabulário diário",
        "audience": "estudante solo",
        "scope": "CLI local com notas",
        "out_of_scope": "app mobile e sync nuvem",
        "constraints": "só local, sem rede",
        "required_data": "lista de palavras do usuário",
        "acceptance": "dá para gravar e revisar 10 cartões offline",
        "risks": "esquecer backup do vault",
    }
    for key, text in answers.items():
        answer_field(brief, key, text)


def test_brief_completo_gera_proposta() -> None:
    brief, _ = start_brief("ferramenta de flashcards offline")
    _fill_all(brief)
    assert not missing_fields(brief)
    assert brief.status == "ready"
    proposal = try_propose(brief)
    assert "Proposta" in proposal
    assert brief.status == "proposed"
    assert "não é plano" in proposal.casefold()


def test_retomada_preserva_respostas(tmp_path: Path) -> None:
    store = BriefStore(tmp_path)
    brief, _ = start_brief("controle de hábitos local")
    answer_field(brief, "objective", "marcar hábitos diários")
    store.save(brief)
    loaded = store.load(brief.id)
    assert loaded.objective == "marcar hábitos diários"
    assert loaded.idea == brief.idea
    assert "audience" in missing_fields(loaded)
    qs = next_questions(loaded)
    assert qs and "público" in qs[0].casefold()


def test_dado_sensivel_marcado_e_cloud_safe() -> None:
    brief, _ = start_brief("app de notas")
    secret = "sk-or-v1-" + ("b" * 24)
    answer_field(brief, "required_data", f"API_KEY={secret}")
    assert "api_key" in brief.sensitive_kinds
    assert secret not in (brief.required_data or "")
    safe = brief.cloud_safe_dict()
    assert safe["required_data"] == "[SENSITIVE_OMITTED]"
    assert secret not in json_dump(safe)


def json_dump(payload: dict) -> str:
    import json

    return json.dumps(payload)


def test_cli_brief_fluxo(tmp_path: Path) -> None:
    runner = CliRunner()
    start = runner.invoke(
        cli,
        ["brief", "start", "agenda", "offline", "--dir", str(tmp_path)],
    )
    assert start.exit_code == 0, start.output
    brief_id = next(
        line.split(":", 1)[1].strip()
        for line in start.output.splitlines()
        if line.startswith("id:")
    )

    incomplete = runner.invoke(cli, ["brief", "propose", brief_id, "--dir", str(tmp_path)])
    assert incomplete.exit_code == 1
    assert "incompleto" in incomplete.output

    for key, text in (
        ("objective", "organizar tarefas do dia"),
        ("audience", "eu mesmo"),
        ("scope", "lista e marcar feito"),
        ("out_of_scope", "calendário compartilhado"),
        ("constraints", "sem nuvem"),
        ("required_data", "títulos das tarefas"),
        ("acceptance", "abre e marca item em menos de 5s"),
        ("risks", "perder o arquivo local"),
    ):
        res = runner.invoke(
            cli,
            ["brief", "answer", brief_id, key, text, "--dir", str(tmp_path)],
        )
        assert res.exit_code == 0, res.output

    proposed = runner.invoke(cli, ["brief", "propose", brief_id, "--dir", str(tmp_path)])
    assert proposed.exit_code == 0, proposed.output
    assert "Proposta" in proposed.output

    show = runner.invoke(
        cli, ["brief", "show", brief_id, "--dir", str(tmp_path), "--cloud-safe"]
    )
    assert show.exit_code == 0
    assert "yby-brief/v1" in show.output
