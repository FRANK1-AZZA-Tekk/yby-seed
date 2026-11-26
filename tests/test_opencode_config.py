"""Configuração OpenCode (ferramenta de engenharia, não runtime): validação offline.

Não instala nem executa o OpenCode. O avaliador abaixo replica a semântica documentada
em opencode.ai/docs/permissions e /policies (lida em 2026-11-26): curingas `*`/`?` sobre o
valor inteiro, padrão de shell terminado em " *" também casa o comando sem argumentos,
última regra que casa vence, e `policies` `tool.use` com deny têm a palavra final.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "opencode.json"
SPEC_PATH = ROOT / "docs" / "OPENCODE_INTEGRATION.md"
PROFILE = "yby-engineer"

# Chaves não obsoletas de https://opencode.ai/config.json (lido em 2026-11-26).
SCHEMA_TOP_LEVEL = {
    "$schema", "agents", "automations", "commands", "compaction", "default_agent",
    "enterprise", "experimental", "formatter", "instructions", "lsp", "mcp", "media",
    "model", "permissions", "plugins", "policies", "providers", "references", "share",
    "shell", "skills", "snapshots", "timezone", "tool_output", "update", "username",
    "warming", "watcher", "websearch", "worktree",
}
DEPRECATED_V1 = {
    "agent", "attachment", "autoshare", "autoupdate", "command", "disabled_providers",
    "enabled_providers", "layout", "logLevel", "mode", "permission", "plugin", "provider",
    "reference", "server", "small_model", "snapshot", "subagent_depth", "tools",
}
AGENT_KEYS = {
    "color", "description", "disabled", "hidden", "mode", "model", "permissions",
    "request", "steps", "system",
}
POLICY_ACTIONS = {
    "provider.use", "tool.use", "integration.connect", "integration.use", "mcp.use",
    "skill.use", "plugin.use", "websearch.use",
}
EFFECTS = {"allow", "deny", "ask"}

# Política base que todo agente recebe antes das regras do projeto (docs: Defaults).
BASE_RULES = [
    {"action": "*", "resource": "*", "effect": "allow"},
    {"action": "read", "resource": "*.env", "effect": "ask"},
    {"action": "read", "resource": "*.env.*", "effect": "ask"},
    {"action": "read", "resource": "*.env.example", "effect": "allow"},
]


@lru_cache(maxsize=1)
def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _compile(pattern: str) -> re.Pattern[str]:
    parts = [".*" if c == "*" else "." if c == "?" else re.escape(c) for c in pattern]
    return re.compile("".join(parts), re.DOTALL)


def _matches(pattern: str, value: str, *, shell_like: bool) -> bool:
    if _compile(pattern).fullmatch(value):
        return True
    return shell_like and pattern.endswith(" *") and value == pattern[:-2]


def _last_effect(rules: list[dict], action: str, resource: str) -> str | None:
    effect = None
    for rule in rules:
        if _matches(rule["action"], action, shell_like=False) and _matches(
            rule["resource"], resource, shell_like=action == "shell"
        ):
            effect = rule["effect"]
    return effect


def _policy_denies(action: str, resource: str) -> bool:
    decision = None
    shell_like = action == "shell"
    for stmt in load_config().get("policies", []):
        if stmt["action"] == "tool.use" and _matches(
            stmt["resource"], f"{action}:{resource}", shell_like=shell_like
        ):
            decision = stmt["effect"]
    return decision == "deny"


def decide(action: str, resource: str) -> str:
    cfg = load_config()
    rules = BASE_RULES + cfg.get("permissions", []) + cfg["agents"][PROFILE].get("permissions", [])
    if resource.startswith(("/", "~")):
        if (_last_effect(rules, "external_directory", resource) or "ask") == "deny":
            return "deny"
    effect = _last_effect(rules, action, resource) or "ask"
    if _policy_denies(action, resource):
        return "deny"
    return effect


# (a) configuração válida, parseável e dentro do schema V2 lido
def test_config_is_valid_json_with_known_v2_keys():
    cfg = load_config()
    assert cfg["$schema"] == "https://opencode.ai/config.json"
    assert set(cfg) <= SCHEMA_TOP_LEVEL
    assert not set(cfg) & DEPRECATED_V1
    assert cfg["share"] == "disabled"


def test_rules_and_policies_have_exact_shape():
    cfg = load_config()
    rule_lists = [cfg["permissions"]] + [
        a.get("permissions", []) for a in cfg["agents"].values()
    ]
    for rules in rule_lists:
        for rule in rules:
            assert set(rule) == {"action", "resource", "effect"}, rule
            assert rule["effect"] in EFFECTS, rule
            assert all(isinstance(v, str) and v for v in rule.values()), rule
    for stmt in cfg["policies"]:
        assert set(stmt) == {"action", "resource", "effect"}, stmt
        assert stmt["action"] in POLICY_ACTIONS, stmt
        assert stmt["effect"] in {"allow", "deny"}, stmt


def test_instructions_reference_existing_rules_without_duplicating_agents_md():
    instructions = load_config()["instructions"]
    assert "AGENTS.md" not in instructions  # carregado automaticamente pelo OpenCode
    for entry in instructions:
        assert not entry.startswith(("http://", "https://", "~", "/")), entry
        assert (ROOT / entry).is_file(), entry


# (b) perfil yby-engineer presente
def test_profile_is_primary_default_and_minimal():
    cfg = load_config()
    assert cfg["default_agent"] == PROFILE
    agent = cfg["agents"][PROFILE]
    assert set(agent) <= AGENT_KEYS
    assert agent["mode"] == "primary"
    assert "AGENTS.md" in agent["description"]
    assert "system" not in agent
    assert "model" not in agent


# (c) permissões restritivas, sem curingas amplos em allow
def test_no_broad_allow_for_shell_or_edit():
    cfg = load_config()
    rules = cfg["permissions"] + cfg["agents"][PROFILE].get("permissions", [])
    for rule in rules:
        if rule["effect"] == "allow":
            assert rule["action"] != "*", rule
            if rule["action"] in {"shell", "edit", "subagent", "external_directory"}:
                assert rule["resource"] != "*", rule


@pytest.mark.parametrize(
    "path,expected",
    [
        ("src/yby/glass/tools.py", "allow"),
        ("src/engine/router.py", "allow"),
        ("tests/test_opencode_config.py", "allow"),
        ("docs/OPENCODE_INTEGRATION.md", "allow"),
        ("src/safety/policy.py", "ask"),
        ("src/security/ast_guard.py", "ask"),
        ("src/actions/__init__.py", "ask"),
        ("README.md", "deny"),
        ("PROGRESS.md", "deny"),
        ("config/safety-allowlist.txt", "deny"),
        ("scripts/install-hub-service.sh", "deny"),
    ],
)
def test_edit_scope(path, expected):
    assert decide("edit", path) == expected


@pytest.mark.parametrize(
    "path,expected",
    [
        ("src/main.py", "allow"),
        ("AGENTS.md", "allow"),
        (".env.example", "allow"),
        ("/etc/passwd", "deny"),
        ("~/.config/opencode/opencode.json", "deny"),
    ],
)
def test_read_scope(path, expected):
    assert decide("read", path) == expected


# (d) comandos de teste permitidos
@pytest.mark.parametrize(
    "command",
    [
        "make check",
        "make doctor",
        "make lint",
        "make test",
        "pytest",
        "pytest tests/test_opencode_config.py -q",
        "python -m pytest tests -q",
        ".venv/bin/python -m pytest tests -q",
        "ruff check src tests",
        "python -m ruff check src tests",
        ".venv/bin/python -m ruff check src tests",
        "git status",
        "git status --short",
        "git diff --check",
        "git diff --check origin/main...HEAD",
    ],
)
def test_verification_commands_allowed(command):
    assert decide("shell", command) == "allow"


@pytest.mark.parametrize(
    "command",
    ["ls", "git commit -m wip", "git diff", "ruff format src", "make check setup", "yby ask oi"],
)
def test_other_commands_ask(command):
    assert decide("shell", command) == "ask"


# (e) comandos destrutivos, instalação e deploy bloqueados
@pytest.mark.parametrize(
    "command",
    [
        "git push",
        "git push -u origin main",
        "git push --force origin main",
        "git merge origin/main",
        "git rebase -i HEAD~3",
        "git reset --hard HEAD",
        "git clean -fdx",
        "git checkout -- src/main.py",
        "git checkout -f main",
        "git checkout .",
        "git restore src/main.py",
        "git switch --discard-changes main",
        "git stash",
        "git stash pop",
        "git stash drop stash@{0}",
        "git branch -D feature",
        "git filter-branch --all",
        "ruff check --fix src",
        "python -m ruff check src --unsafe-fixes",
        "pip install requests",
        "python -m pip install -r requirements.txt",
        ".venv/bin/pip install x",
        "uv pip install x",
        "npm install",
        "npx some-tool",
        "apt-get install jq",
        "make setup",
        "make install-dev",
        "make qdrant-up",
        "make clean",
        "sudo ls",
        "curl https://example.com",
        "wget https://example.com/x",
        "docker compose up -d",
        "systemctl --user restart yby-hub",
        "bash scripts/install-hub-service.sh",
        "vercel deploy --prod",
        "gh pr merge 1",
        "ssh host",
        "rm -rf /",
        "rm -fr data",
        "opencode run hello",
        "ollama pull qwen",
    ],
)
def test_destructive_and_install_commands_denied(command):
    assert decide("shell", command) == "deny"


# (f) segredos e .env bloqueados
@pytest.mark.parametrize(
    "path",
    [".env", "config/.env", ".env.local", ".git/config", "server.pem", "deploy.key",
     "home/.ssh/id_rsa", "aws_credentials.json", "client_secret.json"],
)
def test_secret_paths_denied_for_read_and_edit(path):
    assert decide("read", path) == "deny"
    assert decide("edit", path) == "deny"


@pytest.mark.parametrize("path", ["src/.env", "tests/.env", "docs/.env.example"])
def test_env_files_inside_editable_dirs_denied(path):
    assert decide("edit", path) == "deny"


@pytest.mark.parametrize(
    "command",
    ["cat .env", "cat config/.env", "source .env", "grep KEY .env.local", "printenv",
     "env", "cat .git/config", "cat ~/.ssh/id_rsa"],
)
def test_secret_reading_commands_denied(command):
    assert decide("shell", command) == "deny"


def test_hard_policies_cover_non_negotiables():
    for action, resource in [
        ("shell", "git push origin main"),
        ("shell", "git push"),
        ("shell", "git reset --hard"),
        ("shell", "git stash pop"),
        ("shell", "pip install x"),
        ("edit", "src/.env"),
        ("read", ".env"),
        ("read", ".git/config"),
        ("subagent", "general"),
    ]:
        assert _policy_denies(action, resource), (action, resource)


# (g) MCP desativado, plugins/skills/subagentes negados
def test_mcp_disabled_by_default():
    cfg = load_config()
    servers = cfg.get("mcp", {}).get("servers", {})
    assert all(s.get("type") != "remote" for s in servers.values())
    assert all(s.get("disabled") is True for s in servers.values())
    deny_all = {(p["action"], p["resource"]) for p in cfg["policies"] if p["effect"] == "deny"}
    assert {("mcp.use", "*"), ("plugin.use", "*"), ("skill.use", "*")} <= deny_all
    assert "plugins" not in cfg


@pytest.mark.parametrize("agent_id", ["general", "explore", PROFILE])
def test_subagents_denied(agent_id):
    assert decide("subagent", agent_id) == "deny"


def test_web_tools_require_approval():
    assert decide("webfetch", "https://opencode.ai/docs/") == "ask"
    assert decide("websearch", "opencode permissions") == "ask"


# (h) nenhuma credencial versionada
SECRET_MARKERS = re.compile(
    r"\{env:|\{file:|apiKey|api_key|sk-[A-Za-z0-9]{8,}|Bearer\s+\S|ghp_|github_pat_"
)


def test_config_has_no_credentials_or_providers():
    raw = CONFIG_PATH.read_text(encoding="utf-8")
    assert not SECRET_MARKERS.search(raw)
    cfg = load_config()
    assert "providers" not in cfg
    assert "model" not in cfg


def test_spec_has_no_credentials():
    assert not SECRET_MARKERS.search(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.mark.skipif(shutil.which("git") is None, reason="git indisponível")
def test_no_env_or_opencode_state_tracked():
    proc = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        pytest.skip("fora de um checkout git")
    tracked = proc.stdout.splitlines()
    for name in tracked:
        base = Path(name).name
        if base == ".env" or base.startswith(".env."):
            assert base == ".env.example", name
        assert not name.startswith(".opencode/"), name


# (i) nenhuma alteração/acoplamento no runtime do YBY
def test_runtime_does_not_reference_opencode():
    offenders = [
        str(p.relative_to(ROOT))
        for p in (ROOT / "src").rglob("*")
        if p.is_file() and p.suffix in {".py", ".yaml", ".yml", ".json", ".toml", ".txt"}
        and "opencode" in p.read_text(encoding="utf-8", errors="ignore").lower()
    ]
    assert offenders == []


@pytest.mark.parametrize(
    "path",
    ["AGENTS.md", ".cursor/rules/yby.mdc", ".github/workflows/ci.yml", "Makefile",
     "requirements.txt", "requirements-dev.txt", "pyproject.toml", "opencode.json",
     ".opencode/agents/x.md", "DECISIONS.md"],
)
def test_governance_files_not_editable(path):
    assert decide("edit", path) == "deny"
