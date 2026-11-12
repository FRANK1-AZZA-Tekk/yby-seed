"""Curadoria ChatML de validated_pairs.jsonl para QLoRA/Vast."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from src.yby_seed.config import get_settings

VALID_ROLES = {"system", "user", "assistant"}


@dataclass
class CuratorReport:
    total_lines: int
    kept: int
    removed_invalid: int
    removed_duplicate: int
    output_path: Path


def _line_hash(record: dict) -> str:
    payload = json.dumps(record, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _validate_chatml(record: dict) -> bool:
    messages = record.get("messages")
    if not isinstance(messages, list) or len(messages) < 2:
        return False
    roles = {m.get("role") for m in messages if isinstance(m, dict)}
    if not roles.issubset(VALID_ROLES):
        return False
    if "user" not in roles or "assistant" not in roles:
        return False
    for message in messages:
        if not isinstance(message, dict):
            return False
        if not str(message.get("content", "")).strip():
            return False
    return True


def curate_dataset(path: Path, *, in_place: bool = True) -> CuratorReport:
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return CuratorReport(0, 0, 0, 0, path)

    kept_records: list[dict] = []
    seen: set[str] = set()
    total = 0
    removed_invalid = 0
    removed_duplicate = 0

    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            total += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                removed_invalid += 1
                continue
            if not _validate_chatml(record):
                removed_invalid += 1
                continue
            digest = _line_hash(record)
            if digest in seen:
                removed_duplicate += 1
                continue
            seen.add(digest)
            kept_records.append(record)

    output = path if in_place else path.with_suffix(".cleaned.jsonl")
    tmp = output.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for record in kept_records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp.replace(output)

    return CuratorReport(
        total_lines=total,
        kept=len(kept_records),
        removed_invalid=removed_invalid,
        removed_duplicate=removed_duplicate,
        output_path=output,
    )


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Curadoria validated_pairs.jsonl")
    parser.add_argument("--path", type=Path, default=settings.datasets_path)
    parser.add_argument("--dry-run", action="store_true", help="Não grava; só relatório")
    args = parser.parse_args(argv)

    if args.dry_run:
        report = curate_dataset(args.path, in_place=False)
        print(
            json.dumps(
                {
                    "dry_run": True,
                    "would_write": str(report.output_path),
                    "total_lines": report.total_lines,
                    "kept": report.kept,
                    "removed_invalid": report.removed_invalid,
                    "removed_duplicate": report.removed_duplicate,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        if report.output_path.exists() and report.output_path.suffix == ".cleaned.jsonl":
            report.output_path.unlink(missing_ok=True)
        return 0

    report = curate_dataset(args.path, in_place=True)
    print(
        f"curadoria concluída: kept={report.kept} invalid={report.removed_invalid} "
        f"dup={report.removed_duplicate} → {report.output_path}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
