"""Envio ao Cursor CLI em worktree — sem push/PR/merge/patch no SEED."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from src.develop.export_md import render_layer_markdown
from src.develop.gate import can_send
from src.develop.schemas import DevelopPlan
from src.develop.store import set_layer_status


@dataclass(frozen=True)
class SendPreview:
    binary: str | None
    argv: list[str]
    worktree: Path
    branch: str
    markdown: str
    blocked: str | None = None


def detect_cursor_bin(*, environ: dict[str, str] | None = None) -> str | None:
    source = environ if environ is not None else dict(os.environ)
    override = (source.get("YBY_CURSOR_BIN") or "").strip()
    if override:
        return override
    for name in ("agent", "cursor-agent", "cursor"):
        found = shutil.which(name)
        if found:
            return found
    return None


def build_argv(binary: str, markdown: str) -> list[str]:
    base = Path(binary).name
    if base == "cursor":
        return [binary, "agent", "--plan", markdown]
    return [binary, "--plan", markdown]


def worktree_paths(plan_id: str, layer_id: str) -> tuple[Path, str]:
    branch = f"yby/develop/{plan_id}/{layer_id}"
    wt = Path.home() / ".cache" / "yby" / "develop" / "wt" / plan_id / layer_id
    return wt, branch


def preview_send(
    plan: DevelopPlan,
    layer_id: str,
    *,
    repo_root: Path,
    environ: dict[str, str] | None = None,
) -> SendPreview:
    ok, reason = can_send(plan, layer_id)
    layer = plan.layer(layer_id)
    assert layer is not None
    md = render_layer_markdown(plan, layer)
    wt, branch = worktree_paths(plan.id, layer_id)
    binary = detect_cursor_bin(environ=environ)
    argv = build_argv(binary, md) if binary else []
    return SendPreview(
        binary=binary,
        argv=argv,
        worktree=wt,
        branch=branch,
        markdown=md,
        blocked=None if ok else reason,
    )


def ensure_worktree(
    *,
    repo_root: Path,
    base_commit: str,
    worktree: Path,
    branch: str,
) -> None:
    worktree.parent.mkdir(parents=True, exist_ok=True)
    if worktree.exists():
        return
    cmd = [
        "git",
        "-C",
        str(repo_root),
        "worktree",
        "add",
        "-b",
        branch,
        str(worktree),
        base_commit or "HEAD",
    ]
    completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        raise RuntimeError(
            f"git worktree falhou: {completed.stderr.strip() or completed.stdout.strip()}"
        )


def send_layer(
    plan: DevelopPlan,
    layer_id: str,
    *,
    repo_root: Path,
    root: Path | None = None,
    dry_run: bool = False,
    confirm: bool = True,
    confirm_fn=None,
    run_fn=None,
    environ: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """Retorna (ok_enviada, mensagem). Exit 0 do Cursor NÃO aceita a camada."""

    preview = preview_send(plan, layer_id, repo_root=repo_root, environ=environ)
    if preview.blocked:
        return False, preview.blocked
    if dry_run:
        return True, (
            f"dry-run bin={preview.binary!r} branch={preview.branch} "
            f"wt={preview.worktree} argv0={preview.argv[:3]!r}"
        )
    if not preview.binary:
        return False, "Cursor CLI ausente (YBY_CURSOR_BIN / agent|cursor-agent|cursor)"
    if confirm:
        ask = confirm_fn or (lambda msg: False)
        if not ask(
            f"Enviar camada {layer_id}?\n"
            f"  bin: {preview.binary}\n"
            f"  branch: {preview.branch}\n"
            f"  worktree: {preview.worktree}\n"
            f"  pacote: {len(preview.markdown)} chars MD"
        ):
            return False, "envio cancelado (confirmação negada)"

    ensure_worktree(
        repo_root=repo_root,
        base_commit=plan.base_commit,
        worktree=preview.worktree,
        branch=preview.branch,
    )
    runner = run_fn or (
        lambda argv, cwd: subprocess.run(
            argv, cwd=cwd, check=False, stdin=None, stdout=None, stderr=None
        )
    )
    completed = runner(preview.argv, preview.worktree)
    code = getattr(completed, "returncode", 0)
    # Sessão interativa retornou → enviada (mesmo com exit 0 ≠ aceita)
    set_layer_status(plan, layer_id, "enviada", root=root)
    return True, f"camada {layer_id} marcada enviada (cursor exit={code}; aceite ainda humano)"
