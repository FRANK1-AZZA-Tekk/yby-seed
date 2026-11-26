"""Backup completo da flash de 16 MB do LILYGO T-Watch S3 Plus com manifesto SHA-256."""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from scripts.twatch.common import (
    DEFAULT_BACKUP_DIR,
    DEFAULT_BAUD,
    FLASH_SIZE_16MB,
    Runner,
    default_runner,
    resolve_esptool_cmd,
    resolve_port,
)


def compute_sha256(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_backup_sha256(bin_path: Path, sha_path: Path) -> bool:
    if not bin_path.is_file() or not sha_path.is_file():
        return False
    expected = sha_path.read_text(encoding="utf-8").strip().split()[0]
    actual = compute_sha256(bin_path)
    return bool(expected) and expected == actual


def run_backup(
    *,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    port: str | None = None,
    baud: int = DEFAULT_BAUD,
    runner: Runner = default_runner,
) -> tuple[Path, Path]:
    """Lê 16 MB da flash via `esptool.py` e gera `<arquivo>.sha256`."""

    resolved_dir = Path(backup_dir)
    resolved_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
    bin_path = resolved_dir / f"twatch-s3-plus-{stamp}.bin"
    sha_path = Path(f"{bin_path}.sha256")

    cmd = [*resolve_esptool_cmd(), "--chip", "esp32s3"]
    resolved_port = resolve_port(port)
    if resolved_port:
        cmd.extend(["--port", resolved_port])
    cmd.extend(["--baud", str(baud), "read_flash", "0x0", FLASH_SIZE_16MB, str(bin_path)])

    res = runner(cmd, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Falha ao executar backup via esptool (exit={res.returncode})")
    if not bin_path.is_file() or bin_path.stat().st_size == 0:
        raise RuntimeError(f"Arquivo de backup vazio ou ausente: {bin_path}")

    digest = compute_sha256(bin_path)
    sha_path.write_text(f"{digest}  {bin_path.name}\n", encoding="utf-8")
    return bin_path, sha_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backup de 16 MB da flash do T-Watch S3 Plus")
    parser.add_argument("--port", default=None, help="Porta serial USB (ex: /dev/ttyACM0)")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help="Velocidade baud")
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    args = parser.parse_args(argv)

    try:
        bin_path, sha_path = run_backup(
            backup_dir=args.backup_dir,
            port=args.port,
            baud=args.baud,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Erro no backup USB: {exc}", file=sys.stderr)
        return 1

    print(f"Backup concluído: {bin_path}")
    print(f"Manifesto SHA-256: {sha_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
