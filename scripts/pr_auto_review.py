#!/usr/bin/env python3
"""Gera comentário de revisão automática para PRs (fallback do Bugbot).

Analisa o diff BASE..HEAD com checagens determinísticas — sem chamar
APIs de nuvem e sem exigir secrets. Escreve `pr-review-comment.md`.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "pr-review-comment.md"

SECRET_PATTERNS = (
    (re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"][^'\"]{8,}"), "possível segredo hardcoded"),
    (re.compile(r"(?i)sk-[A-Za-z0-9]{20,}"), "padrão de chave sk-…"),
    (re.compile(r"(?i)xai-[A-Za-z0-9]{20,}"), "padrão de chave xai-…"),
)

LEGACY_TOUCH = (
    "src/agents/",
    "src/rag/",
    "src/gateway/",
    "src/core/",
)

CODE_GLOBS = (".py",)
DOC_HINTS = ("README", "docs/", "DECISIONS", "AGENTS", ".mdc", "DEV.md", "CI.md")
TEST_HINTS = ("tests/", "test_")


def _run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, cwd=ROOT, text=True, stderr=subprocess.STDOUT)


def changed_files(base: str, head: str) -> list[str]:
    out = _run(["git", "diff", "--name-only", f"{base}...{head}"])
    return [line.strip() for line in out.splitlines() if line.strip()]


def diff_text(base: str, head: str) -> str:
    return _run(["git", "diff", f"{base}...{head}"])


def main() -> int:
    base = os.environ.get("BASE_SHA") or os.environ.get("GITHUB_BASE_REF")
    head = os.environ.get("HEAD_SHA") or "HEAD"
    if not base:
        # Fallback local: comparar com main se existir.
        try:
            base = _run(["git", "merge-base", "origin/main", "HEAD"]).strip()
        except subprocess.CalledProcessError:
            base = "HEAD~1"

    files = changed_files(base, head)
    diff = diff_text(base, head)

    findings: list[str] = []
    notes: list[str] = []

    if not files:
        notes.append("Nenhum arquivo no diff (ou base/head iguais).")
    else:
        notes.append(f"{len(files)} arquivo(s) alterado(s).")

    for path in files:
        if any(path.startswith(p) or f"/{p}" in path for p in LEGACY_TOUCH):
            findings.append(
                f"- Toque em legado `{path}` — confirme que a tarefa pediu isso "
                "(AGENTS.md: não expandir agents/rag/gateway sem pedido)."
            )

    for pattern, label in SECRET_PATTERNS:
        # Só linhas adicionadas.
        for line in diff.splitlines():
            if not line.startswith("+") or line.startswith("+++"):
                continue
            if pattern.search(line):
                findings.append(f"- Possível vazamento ({label}): `{line[1:80]}…`")
                break

    code_changed = any(f.endswith(CODE_GLOBS) and not f.startswith("tests/") for f in files)
    tests_changed = any(
        any(h in f for h in TEST_HINTS) or f.startswith("tests/") for f in files
    )
    docs_changed = any(any(h in f for h in DOC_HINTS) for f in files)

    if code_changed and not tests_changed:
        findings.append(
            "- Código Python fora de `tests/` mudou sem alteração de testes — "
            "adicione/ajuste teste ou justifique no PR."
        )
    if code_changed and not docs_changed:
        notes.append(
            "Código mudou sem docs/regras no diff — atualize README/docs se o "
            "comportamento visível mudou (regra yby.mdc)."
        )

    # Bloqueadores leves: só reportamos; o CI (doctor/lint/test) é quem falha o PR.
    status = "atenção" if findings else "ok"
    lines = [
        "<!-- yby-seed-auto-review -->",
        "## Revisão automática YBY SEED",
        "",
        f"**Status:** `{status}`",
        "",
        "Checagens determinísticas (sem nuvem). O job **CI** (`make doctor` / "
        "`make lint` / `make test`) é o gate bloqueante.",
        "",
        "### Observações",
        "",
    ]
    lines.extend(f"- {n}" for n in notes)
    if findings:
        lines.extend(["", "### Achados", ""])
        lines.extend(findings)
    else:
        lines.extend(["", "Nenhum achado automático além das observações.", ""])

    lines.extend(
        [
            "",
            "### Checklist rápido",
            "",
            "- [ ] Escopo limitado aos arquivos da tarefa",
            "- [ ] Sem recursos fictícios / docs prometendo o que não existe",
            "- [ ] Sem APIs de nuvem novas sem auth + log local",
            "- [ ] Código gerado não executado fora de sandbox + aprovação",
            "- [ ] Teste + docs quando o comportamento muda",
            "",
            "### Bugbot / Cursor",
            "",
            "Se o Cursor Bugbot estiver habilitado no repo, use-o como revisão "
            "principal. Como ativar: ver `docs/CI.md`.",
            "",
            f"_base=`{base[:12]}` head=`{head[:12]}`_",
        ]
    )

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(exc.output, file=sys.stderr)
        raise SystemExit(1) from exc
