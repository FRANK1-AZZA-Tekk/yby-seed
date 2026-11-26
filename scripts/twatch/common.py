"""Helpers compartilhados para os scripts CLI do T-Watch S3 Plus (6A)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIRMWARE_DIR = REPO_ROOT / "firmware" / "twatch_s3_plus"
DEFAULT_BACKUP_DIR = REPO_ROOT / "backups" / "twatch"
FLASH_SIZE_16MB = "0x1000000"
DEFAULT_BAUD = 921600
DEFAULT_MONITOR_BAUD = 115200

Runner = Callable[..., subprocess.CompletedProcess[str]]


def resolve_port(port: str | None) -> str | None:
    candidate = (port if port is not None else os.environ.get("YBY_TWATCH_PORT", "")).strip()
    return candidate or None


def resolve_pio_executable() -> str:
    return shutil.which("pio") or shutil.which("platformio") or "pio"


def resolve_esptool_cmd() -> list[str]:
    exe = shutil.which("esptool.py") or shutil.which("esptool")
    if exe:
        return [exe]
    return [sys.executable, "-m", "esptool"]


def default_runner(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, **kwargs)  # type: ignore[arg-type]
