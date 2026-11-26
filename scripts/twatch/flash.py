"""Gravação USB do T-Watch S3 Plus com trava obrigatória de backup prévio (D10)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.twatch.backup import verify_backup_sha256
from scripts.twatch.common import (
    DEFAULT_BACKUP_DIR,
    DEFAULT_FIRMWARE_DIR,
    Runner,
    default_runner,
    resolve_pio_executable,
    resolve_port,
)


def find_valid_backup(backup_dir: Path) -> Path | None:
    if not backup_dir.is_dir():
        return None
    candidates = sorted(
        backup_dir.glob("twatch-s3-plus-*.bin"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for bin_path in candidates:
        sha_path = Path(f"{bin_path}.sha256")
        if verify_backup_sha256(bin_path, sha_path):
            return bin_path
    return None


def run_flash(
    *,
    firmware_dir: Path = DEFAULT_FIRMWARE_DIR,
    backup_dir: Path = DEFAULT_BACKUP_DIR,
    env_name: str = "lilygo-twatch-s3-plus",
    port: str | None = None,
    skip_backup: bool = False,
    runner: Runner = default_runner,
) -> int:
    if not skip_backup:
        found = find_valid_backup(Path(backup_dir))
        if found is None:
            raise RuntimeError(
                "Nenhum backup válido encontrado em "
                f"{backup_dir}. Rode `make twatch-backup` antes de gravar "
                "ou passe `--skip-backup` explicitamente."
            )

    cmd = [
        resolve_pio_executable(),
        "run",
        "-d",
        str(firmware_dir),
        "-e",
        env_name,
        "-t",
        "upload",
    ]
    resolved_port = resolve_port(port)
    if resolved_port:
        cmd.extend(["--upload-port", resolved_port])
    res = runner(cmd, text=True)
    return int(res.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Grava firmware no T-Watch S3 Plus via USB")
    parser.add_argument("--firmware-dir", type=Path, default=DEFAULT_FIRMWARE_DIR)
    parser.add_argument("--backup-dir", type=Path, default=DEFAULT_BACKUP_DIR)
    parser.add_argument("--env", default="lilygo-twatch-s3-plus")
    parser.add_argument("--port", default=None, help="Porta serial USB (ex: /dev/ttyACM0)")
    parser.add_argument(
        "--skip-backup",
        action="store_true",
        help="Ignora a trava de backup prévio de 16 MB (uso consciente)",
    )
    args = parser.parse_args(argv)

    try:
        rc = run_flash(
            firmware_dir=args.firmware_dir,
            backup_dir=args.backup_dir,
            env_name=args.env,
            port=args.port,
            skip_backup=args.skip_backup,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Erro no flash USB: {exc}", file=sys.stderr)
        return 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
