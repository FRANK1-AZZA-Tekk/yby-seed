"""Compilação PlatformIO do firmware do T-Watch S3 Plus."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.twatch.common import (
    DEFAULT_FIRMWARE_DIR,
    Runner,
    default_runner,
    resolve_pio_executable,
)


def run_build(
    *,
    firmware_dir: Path = DEFAULT_FIRMWARE_DIR,
    env_name: str = "lilygo-twatch-s3-plus",
    runner: Runner = default_runner,
) -> int:
    cmd = [resolve_pio_executable(), "run", "-d", str(firmware_dir), "-e", env_name]
    res = runner(cmd, text=True)
    return int(res.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compila o firmware do T-Watch S3 Plus via PlatformIO")
    parser.add_argument("--firmware-dir", type=Path, default=DEFAULT_FIRMWARE_DIR)
    parser.add_argument("--env", default="lilygo-twatch-s3-plus")
    args = parser.parse_args(argv)

    rc = run_build(firmware_dir=args.firmware_dir, env_name=args.env)
    if rc != 0:
        print(f"Falha na compilação PlatformIO (exit={rc})", file=sys.stderr)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
