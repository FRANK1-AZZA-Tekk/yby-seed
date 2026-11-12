"""Pré-voo do dataset ChatML e registro GGUF no Ollama local."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from src.yby_seed.config import get_settings
from src.yby_seed.forge.dataset_synth_prompts import SYNTH_SYSTEM

VALID_ROLES = frozenset({"system", "user", "assistant"})
MAX_TOKENS_ESTIMATE = 8192
GGUF_MAGIC = b"GGUF"
# IQ4 ~4GB é plausível na GTX 1650; acima disso provavelmente estoura VRAM.
GGUF_WARN_BYTES = 4 * 1024**3
GGUF_BLOCK_BYTES = 4 * 1024**3

CHATML_TEMPLATE = '''TEMPLATE """{{ if .System }}<|im_start|>system
{{ .System }}
{{ end }}{{ if .Prompt }}<|im_start|>user
{{ .Prompt }}
{{ end }}<|im_start|>assistant
"""'''

DEFAULT_MODEL_NAME = "yby-seed-coder:latest"


def yby_coder_system_prompt() -> str:
    """Prompt canônico alinhado a docs/yby_seed_contracts.md e síntese de dataset."""
    return (
        "Você é o coder local YBY SEED (Function Over Form, GTX 1650 4 GB VRAM). "
        "Siga docs/yby_seed_contracts.md.\n"
        f"{SYNTH_SYSTEM.strip()}"
    )


def estimate_tokens(record: dict) -> int:
    messages = record.get("messages", [])
    total = 0
    for message in messages:
        if isinstance(message, dict):
            total += len(str(message.get("content", "")))
    return total // 4


def _validate_chatml_record(record: dict) -> str | None:
    messages = record.get("messages")
    if not isinstance(messages, list) or not messages:
        return "messages ausente ou vazio"
    roles_present: set[str] = set()
    for idx, message in enumerate(messages):
        if not isinstance(message, dict):
            return f"mensagem {idx}: não é objeto"
        role = message.get("role")
        if role not in VALID_ROLES:
            return f"mensagem {idx}: role inválido {role!r}"
        roles_present.add(str(role))
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            return f"mensagem {idx}: content vazio"
    required = {"system", "user", "assistant"}
    if not required.issubset(roles_present):
        missing = ", ".join(sorted(required - roles_present))
        return f"roles obrigatórios ausentes: {missing}"
    for message in messages:
        if message.get("role") == "assistant" and not str(message.get("content", "")).strip():
            return "assistant content vazio"
    if estimate_tokens(record) > MAX_TOKENS_ESTIMATE:
        return f"estimativa de tokens > {MAX_TOKENS_ESTIMATE}"
    return None


@dataclass
class PreflightReport:
    path: Path
    min_samples: int
    valid_count: int = 0
    line_errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        if self.line_errors:
            return False
        if self.valid_count < self.min_samples:
            return False
        return True

    def summary_errors(self) -> list[str]:
        errors = list(self.line_errors)
        if self.valid_count < self.min_samples:
            errors.append(
                f"mínimo de amostras não atingido: {self.valid_count} < {self.min_samples}"
            )
        return errors


def preflight_dataset(jsonl_path: Path, *, min_samples: int = 1) -> PreflightReport:
    report = PreflightReport(path=jsonl_path, min_samples=min_samples)
    if not jsonl_path.is_file():
        report.line_errors.append(f"arquivo não encontrado: {jsonl_path}")
        return report

    line_no = 0
    with jsonl_path.open(encoding="utf-8") as handle:
        for raw in handle:
            line_no += 1
            line = raw.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                report.line_errors.append(f"linha {line_no}: JSON inválido ({exc.msg})")
                continue
            if not isinstance(record, dict):
                report.line_errors.append(f"linha {line_no}: registro não é objeto JSON")
                continue
            err = _validate_chatml_record(record)
            if err:
                report.line_errors.append(f"linha {line_no}: {err}")
                continue
            report.valid_count += 1

    return report


def verify_gguf_file(gguf_path: Path) -> tuple[list[str], list[str]]:
    """Retorna (warnings, blockers)."""
    warnings: list[str] = []
    blockers: list[str] = []
    if not gguf_path.is_file():
        blockers.append(f"GGUF não encontrado: {gguf_path}")
        return warnings, blockers
    size = gguf_path.stat().st_size
    if size == 0:
        blockers.append("GGUF vazio")
        return warnings, blockers
    try:
        with gguf_path.open("rb") as handle:
            magic = handle.read(4)
        if magic != GGUF_MAGIC:
            blockers.append("cabeçalho GGUF inválido (magic GGUF esperado)")
    except OSError as exc:
        blockers.append(f"leitura GGUF falhou: {exc}")

    if size >= GGUF_BLOCK_BYTES:
        blockers.append(f"tamanho {size} bytes excede limite GTX 1650 (~{GGUF_BLOCK_BYTES} bytes)")
    elif size >= GGUF_WARN_BYTES:
        warnings.append(
            f"tamanho {size} bytes próximo do teto de 4 GB VRAM — verifique IQ4/quantização"
        )
    return warnings, blockers


def build_modelfile_content(
    gguf_path: Path,
    *,
    system_prompt: str | None = None,
    num_ctx: int = 4096,
    temperature: float = 0.1,
) -> str:
    resolved = gguf_path.expanduser().resolve()
    raw_system = (system_prompt or yby_coder_system_prompt()).strip()
    system = (
        raw_system.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")
    )
    lines = [
        f"FROM {resolved}",
        f"PARAMETER num_ctx {num_ctx}",
        f"PARAMETER temperature {temperature}",
        f'SYSTEM "{system}"',
        CHATML_TEMPLATE,
    ]
    return "\n".join(lines) + "\n"


@dataclass
class RegisterReport:
    model_name: str
    modelfile_path: Path
    modelfile_text: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    created: bool = False


def register_gguf_in_ollama(
    gguf_path: Path,
    model_name: str = DEFAULT_MODEL_NAME,
    *,
    dry_run: bool = False,
    modelfile_dir: Path | None = None,
) -> RegisterReport:
    warnings, blockers = verify_gguf_file(gguf_path)
    modelfile_text = build_modelfile_content(gguf_path)
    target_dir = modelfile_dir or Path("data/models")
    target_dir.mkdir(parents=True, exist_ok=True)
    modelfile_path = target_dir / f"Modelfile.{model_name.replace(':', '_')}"

    report = RegisterReport(
        model_name=model_name,
        modelfile_path=modelfile_path,
        modelfile_text=modelfile_text,
        warnings=warnings,
        errors=list(blockers),
    )
    if blockers:
        return report

    if dry_run:
        return report

    modelfile_path.write_text(modelfile_text, encoding="utf-8")
    try:
        proc = subprocess.run(
            ["ollama", "create", model_name, "-f", str(modelfile_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        report.errors.append("comando ollama não encontrado no PATH")
        return report

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip()
        report.errors.append(f"ollama create falhou (exit {proc.returncode}): {detail}")
        return report

    report.created = True
    return report


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        description="Pré-voo validated_pairs.jsonl e registro GGUF no Ollama"
    )
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Auditar JSONL ChatML antes de QLoRA/Vast",
    )
    parser.add_argument(
        "--register",
        type=Path,
        nargs="?",
        const=Path("./data/models/YBY-SEED-Coder-7B-IQ4_XS.gguf"),
        help="Registra GGUF no Ollama (caminho opcional)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Não executa ollama create (só gera/valida Modelfile)",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=settings.datasets_path,
        help="Caminho do dataset ChatML",
    )
    parser.add_argument(
        "--min-samples",
        type=int,
        default=1,
        help="Mínimo de amostras válidas exigido no pré-voo",
    )
    parser.add_argument(
        "--model-name",
        default=DEFAULT_MODEL_NAME,
        help="Nome do modelo no Ollama",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.preflight and args.register is None:
        build_parser().print_help()
        return 2

    exit_code = 0

    if args.preflight:
        report = preflight_dataset(args.jsonl, min_samples=args.min_samples)
        payload = {
            "ok": report.ok,
            "path": str(report.path),
            "valid_count": report.valid_count,
            "min_samples": report.min_samples,
            "errors": report.summary_errors(),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if not report.ok:
            exit_code = 1

    if args.register is not None:
        reg = register_gguf_in_ollama(
            args.register,
            model_name=args.model_name,
            dry_run=args.dry_run,
        )
        payload = {
            "model_name": reg.model_name,
            "modelfile": str(reg.modelfile_path),
            "warnings": reg.warnings,
            "errors": reg.errors,
            "created": reg.created,
            "dry_run": args.dry_run,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if reg.errors:
            exit_code = 1
        elif args.dry_run:
            print(reg.modelfile_text)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
