"""Porta de segurança: run, ask e refuse, sem executar comandos."""

from __future__ import annotations

from pathlib import Path

from src.safety.policy import Decision, confirm, decide, load_policy

ALLOWLIST = """
[read]
ls
cat
df

[git]
git

[scripts]
scripts

[refuse]
rm -rf /
git push --force
"""


def _policy(tmp_path: Path):
    path = tmp_path / "allowlist.txt"
    path.write_text(ALLOWLIST, encoding="utf-8")
    return load_policy(path)


def test_leitura_git_e_script_rodam(tmp_path: Path) -> None:
    policy = _policy(tmp_path)
    script = tmp_path / "scripts" / "ok.py"
    script.parent.mkdir()
    script.write_text("print('ok')\n", encoding="utf-8")

    assert decide("ls -la", policy=policy, project_root=tmp_path).action == "run"
    assert decide("df -h", policy=policy, project_root=tmp_path).action == "run"
    assert decide("cat README.md", policy=policy, project_root=tmp_path).action == "run"
    assert decide("git status", policy=policy, project_root=tmp_path).action == "run"
    assert decide("git diff", policy=policy, project_root=tmp_path).action == "run"
    decision = decide(f"python {script}", policy=policy, project_root=tmp_path)
    assert decision.action == "run"
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
