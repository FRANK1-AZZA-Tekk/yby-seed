"""Porta de segurança: run, ask e refuse, sem executar comandos."""

from __future__ import annotations

from pathlib import Path

from src.safety.policy import Decision, confirm, decide, load_policy

ALLOWLIST = """
[read]
ls
cat
df
date

[git]
git

[scripts]
scripts

[refuse]
rm -rf /
git push --force
git reset --hard
git clean -fd
"""


def _policy(tmp_path: Path):
    path = tmp_path / "allowlist.txt"
    path.write_text(ALLOWLIST, encoding="utf-8")
    return load_policy(path)


def test_leitura_e_git_inspecao_rodam(tmp_path: Path) -> None:
    policy = _policy(tmp_path)

    assert decide("ls -la", policy=policy, project_root=tmp_path).action == "run"
    assert decide("df -h", policy=policy, project_root=tmp_path).action == "run"
    assert decide("cat README.md", policy=policy, project_root=tmp_path).action == "run"
    assert decide("git status", policy=policy, project_root=tmp_path).action == "run"
    assert decide("git diff", policy=policy, project_root=tmp_path).action == "run"


def test_script_do_projeto_pede_confirmacao(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    script = tmp_path / "scripts" / "ok.py"
    script.parent.mkdir()
    script.write_text("print('ok')\n", encoding="utf-8")

    decision = decide(f"python {script}", policy=policy, project_root=tmp_path)
    assert decision.action == "ask"
    assert "script do projeto" in decision.reason


def test_fora_da_allowlist_pede_confirmacao(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    decision = decide("rm arquivo.txt", policy=policy, project_root=tmp_path)
    assert decision.action == "ask"

    answers = iter(["s"])
    said: list[str] = []
    approved = confirm(
        "rm arquivo.txt",
        decision,
        input_fn=lambda: next(answers),
        output_fn=said.append,
    )
    assert approved
    assert any("s/n" in line for line in said)

    said.clear()
    assert confirm(
        "rm arquivo.txt",
        decision,
        input_fn=lambda: "não",
        output_fn=said.append,
    ) is False


def test_destrutivo_e_recusado_sem_perguntar(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    decision = decide("rm -rf /", policy=policy, project_root=tmp_path)
    assert decision.action == "refuse"
    asked = {"sim": False}

    def _boom() -> str:
        asked["sim"] = True
        return "s"

    assert confirm("rm -rf /", decision, input_fn=_boom, output_fn=lambda _line: None) is False
    assert asked["sim"] is False


def test_rm_de_arquivo_nao_casa_com_a_raiz(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    assert decide("rm -rf /tmp/cache", policy=policy, project_root=tmp_path).action == "ask"


def test_git_forcado_e_recusado(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    decision = decide(
        "git push --force origin main",
        policy=policy,
        project_root=tmp_path,
    )
    assert decision.action == "refuse"


def test_script_fora_da_pasta_pede_confirmacao(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    outside = tmp_path.parent / "fora.py"
    outside.write_text("print(1)\n", encoding="utf-8")
    assert decide(f"python {outside}", policy=policy, project_root=tmp_path).action == "ask"


def test_allowlist_padrao_existe() -> None:
    from src.safety.policy import default_policy_path

    policy = load_policy(default_policy_path())
    assert "ls" in policy.read_only
    assert "git" in policy.git
    assert any("rm -rf /" in item for item in policy.refuse)


def test_run_nao_pede_input() -> None:
    decision = Decision("run", "comando somente leitura: ls")
    assert confirm("ls", decision, input_fn=lambda: "n", output_fn=lambda _line: None) is True


def test_git_config_inline_pede_confirmacao(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    assert decide("git -c color.ui=false status", policy=policy, project_root=tmp_path).action == "ask"
    assert decide("git config user.name x", policy=policy, project_root=tmp_path).action == "ask"
    assert decide("git commit -m x", policy=policy, project_root=tmp_path).action == "ask"


def test_git_alias_shell_e_recusado(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    decision = decide(
        "git -c alias.x=!id x",
        policy=policy,
        project_root=tmp_path,
    )
    assert decision.action == "refuse"
    assert "alias" in decision.reason or "!" in decision.reason or "shell" in decision.reason


def test_refuse_apos_aspas_no_argv(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    decision = decide("bash -c 'rm -rf /'", policy=policy, project_root=tmp_path)
    assert decision.action == "refuse"
    assert "rm -rf /" in decision.reason


def test_git_status_e_ls_continuam_run(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    assert decide("git status", policy=policy, project_root=tmp_path).action == "run"
    assert decide("ls", policy=policy, project_root=tmp_path).action == "run"


def test_git_path_falso_pede_confirmacao(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    fake = tmp_path / "bin" / "git"
    fake.parent.mkdir()
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    decision = decide(f"{fake} status", policy=policy, project_root=tmp_path)
    assert decision.action == "ask"
    assert "caminho" in decision.reason


def test_date_set_pede_confirmacao(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    assert decide("date", policy=policy, project_root=tmp_path).action == "run"
    assert decide("date --set=2030-01-01", policy=policy, project_root=tmp_path).action == "ask"
    assert decide("date -s 2030-01-01", policy=policy, project_root=tmp_path).action == "ask"


def test_git_reset_hard_com_pager_e_recusado(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    assert decide("git --no-pager reset --hard", policy=policy, project_root=tmp_path).action == "refuse"
    assert decide("git reset --hard", policy=policy, project_root=tmp_path).action == "refuse"


def test_git_repo_alternativo_pede_confirmacao(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    assert decide("git -C /tmp status", policy=policy, project_root=tmp_path).action == "ask"
    assert decide("git --git-dir=/tmp/x.git status", policy=policy, project_root=tmp_path).action == "ask"


def test_git_push_sem_force_pede_confirmacao(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    assert decide("git push origin main", policy=policy, project_root=tmp_path).action == "ask"
    assert decide("git push --force origin main", policy=policy, project_root=tmp_path).action == "refuse"


def test_ask_sem_interacao_nao_aprova(tmp_path: Path) -> None:
    decision = Decision("ask", "fora da allowlist")
    said: list[str] = []

    def _eof() -> str:
        raise EOFError

    assert confirm("rm x", decision, input_fn=_eof, output_fn=said.append) is False
    assert any("interação" in line.casefold() or "interacao" in line.casefold() for line in said)
