"""Porta de segurança: run, ask e refuse, sem executar comandos."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_git_destrutivo_com_flags_fora_de_ordem() -> None:
    from src.safety.policy import default_policy_path

    policy = load_policy(default_policy_path())
    root = Path(__file__).resolve().parents[1]
    assert decide("git push origin --force", policy=policy, project_root=root).action == "refuse"
    assert decide("git -C /tmp push -f origin", policy=policy, project_root=root).action == "refuse"
    assert decide("git reset HEAD --hard", policy=policy, project_root=root).action == "refuse"
    assert decide("git clean -df", policy=policy, project_root=root).action == "refuse"
    assert decide("git status", policy=policy, project_root=root).action == "run"
    assert decide("git diff", policy=policy, project_root=root).action == "run"
    assert decide("git push origin main", policy=policy, project_root=root).action == "ask"
    assert decide("git commit -m x", policy=policy, project_root=root).action == "ask"
    assert decide("git checkout .", policy=policy, project_root=root).action == "ask"
    assert decide("git branch -D feature", policy=policy, project_root=root).action == "ask"
    glued = decide("git push origin --force && true", policy=policy, project_root=root)
    assert glued.action == "refuse"


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


# --- Segredos e git -c na allowlist ------------------------------------------
# Política (D10: menor privilégio, confirmação humana, recusa segura):
#   cat/head/tail da seção [read] só rodam direto se TODOS os caminhos ficarem
#   dentro do projeto (links simbólicos resolvidos) e não casarem com um padrão
#   sensível (piso em policy.py + seção [sensitive] da allowlist). Caso
#   contrário a decisão é `ask`: nunca `run` sem confirmação.
#   git de leitura vira `ask` com -c/--config-env/--exec-path (executam código
#   ou trocam config), --no-index (lê fora do repositório), -O (abre programa
#   externo) ou quando o argumento aponta para arquivo sensível.
#   O padrão sensível é um piso, não prova de que o resto é seguro.


def _real_policy():
    from src.safety.policy import default_policy_path

    return load_policy(default_policy_path())


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "projeto"
    (root / "docs").mkdir(parents=True)
    (root / "README.md").write_text("ok\n", encoding="utf-8")
    (root / "docs" / "DEV.md").write_text("ok\n", encoding="utf-8")
    (root / ".env").write_text("TOKEN=falso\n", encoding="utf-8")
    return root


@pytest.mark.parametrize(
    "command",
    [
        "cat .env",
        "head -c 10 .env",
        "tail -n 1 .env",
        "cat ~/.ssh/id_rsa",
        "cat ~/.ssh/id_ed25519",
        "cat /etc/shadow",
        "cat /etc/passwd",
        "cat ../fora.txt",
        "cat .env.local",
        "cat config/.env.production",
        "cat prod.env",
        "cat deploy/id_rsa",
        "cat certs/server.pem",
        "cat certs/server.key",
        "cat .ssh/config",
        "cat .git/config",
        "cat .netrc",
        "cat .aws/credentials",
        "cat secrets.yaml",
        "cat .ENV",
        "cat -- .env",
        "cat README.md .env",
        "cat $HOME/.ssh/id_rsa",
        "cat .e*",
    ],
)
def test_leitura_de_segredo_nunca_roda_direto(tmp_path: Path, command: str) -> None:
    root = _project(tmp_path)
    decision = decide(command, policy=_real_policy(), project_root=root)
    assert decision.action in {"ask", "refuse"}, decision


def test_leitura_sensivel_pede_confirmacao_antes_de_executar(tmp_path: Path) -> None:
    root = _project(tmp_path)
    decision = decide("cat .env", policy=_real_policy(), project_root=root)
    assert decision.action == "ask"

    said: list[str] = []
    assert confirm("cat .env", decision, input_fn=lambda: "n", output_fn=said.append) is False
    assert any("s/n" in line for line in said)
    assert confirm("cat .env", decision, input_fn=lambda: "s", output_fn=lambda _l: None) is True


def test_link_simbolico_para_fora_ou_para_segredo_pede_confirmacao(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "atalho.txt").symlink_to(root / ".env")
    (root / "fora.txt").symlink_to("/etc/passwd")
    policy = _real_policy()
    assert decide("cat atalho.txt", policy=policy, project_root=root).action == "ask"
    assert decide("cat fora.txt", policy=policy, project_root=root).action == "ask"


@pytest.mark.parametrize(
    "command",
    [
        "cat README.md",
        "cat docs/DEV.md",
        "cat ./docs/DEV.md",
        "head -n 5 README.md",
        "tail -n 5 docs/DEV.md",
        "cat src/safety/policy.py",
        "ls -la",
        "ls ~/.ssh",
        "git status",
        "git diff",
        "git log --oneline -n 5",
        "git show HEAD:README.md",
        "git log -c",
        "git diff -- docs/DEV.md",
    ],
)
def test_leitura_legitima_dentro_do_projeto_continua_run(tmp_path: Path, command: str) -> None:
    root = _project(tmp_path)
    decision = decide(command, policy=_real_policy(), project_root=root)
    assert decision.action == "run", decision


@pytest.mark.parametrize(
    "command",
    [
        "git -c core.pager=x log",
        "git -c core.fsmonitor=x status",
        "git --config-env=core.pager=X log",
        "git --config-env core.pager=X log",
        "git --exec-path=/tmp/x status",
        "git -C . -c core.pager=x log",
        "git --no-index diff /etc/shadow /dev/null",
        "git diff --no-index /etc/shadow /dev/null",
        "git grep -Ocat KEY",
        "git grep --open-files-in-pager=cat KEY",
        "git show HEAD:.env",
        "git log -p -- .env",
        "git diff -- .ssh/id_rsa",
    ],
)
def test_git_perigoso_nao_roda_automaticamente(tmp_path: Path, command: str) -> None:
    root = _project(tmp_path)
    decision = decide(command, policy=_real_policy(), project_root=root)
    assert decision.action == "ask", decision


def test_piso_sensivel_vale_sem_secao_sensitive(tmp_path: Path) -> None:
    root = _project(tmp_path)
    policy = _policy(tmp_path)
    assert policy.sensitive == ()
    assert decide("cat .env", policy=policy, project_root=root).action == "ask"
    assert decide("cat README.md", policy=policy, project_root=root).action == "run"


def test_secao_sensitive_da_allowlist_amplia_o_piso(tmp_path: Path) -> None:
    path = tmp_path / "allowlist.txt"
    path.write_text(ALLOWLIST + "\n[sensitive]\nminha-chave.txt\n", encoding="utf-8")
    policy = load_policy(path)
    root = _project(tmp_path)
    assert policy.sensitive == ("minha-chave.txt",)
    assert decide("cat minha-chave.txt", policy=policy, project_root=root).action == "ask"
    assert decide("cat README.md", policy=policy, project_root=root).action == "run"


def test_refuse_continua_valendo_para_leitura_de_segredo(tmp_path: Path) -> None:
    root = _project(tmp_path)
    decision = decide("cat .env && rm -rf /", policy=_policy(tmp_path), project_root=root)
    assert decision.action == "refuse"
    asked = {"sim": False}

    def _boom() -> str:
        asked["sim"] = True
        return "s"

    assert confirm("cat .env && rm -rf /", decision, input_fn=_boom, output_fn=lambda _l: None) is False
    assert asked["sim"] is False
