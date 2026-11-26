"""Monitor serial USB do T-Watch S3 Plus via PlatformIO."""

from __future__ import annotations

import argparse
from pathlib import Path

from scripts.twatch.common import (
    DEFAULT_FIRMWARE_DIR,
    DEFAULT_MONITOR_BAUD,
    Runner,
    default_runner,
    resolve_pio_executable,
    resolve_port,
)


def run_monitor(
    *,
    firmware_dir: Path = DEFAULT_FIRMWARE_DIR,
    port: str | None = None,
    baud: int = DEFAULT_MONITOR_BAUD,
    runner: Runner = default_runner,
) -> int:
    cmd = [
        resolve_pio_executable(),
        "device",
        "monitor",
        "-d",
        str(firmware_dir),
        "-b",
        str(baud),
    ]
    resolved_port = resolve_port(port)
    if resolved_port:
        cmd.extend(["-p", resolved_port])
    res = runner(cmd, text=True)
    return int(res.returncode)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Abre monitor serial do T-Watch S3 Plus")
    parser.add_argument("--firmware-dir", type=Path, default=DEFAULT_FIRMWARE_DIR)
    parser.add_argument("--port", default=None)
    parser.add_argument("--baud", type=int, default=DEFAULT_MONITOR_BAUD)
    args = parser.parse_args(argv)
    return run_monitor(firmware_dir=args.firmware_dir, port=args.port, baud=args.baud)


if __name__ == "__main__":
    raise SystemExit(main())
