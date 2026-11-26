#!/usr/bin/env python3
"""Backup, dump e flash do LILYGO T-Watch S3 Plus (ESP32-S3) via USB.

    uv run python scripts/twatch/flash_manager.py backup --port /dev/ttyACM0 \
        --out backups/twatch_factory.bin
    python3 scripts/twatch/flash_manager.py build-and-flash --project-dir ../twatch-fw \
        --port /dev/ttyACM0

Ferramenta de bancada para o dispositivo do próprio usuário: lê a flash com `esptool.py`
(somente `read_flash`) e compila/grava com PlatformIO, sempre com o MVP sem LoRa
(`-DYBY_LORA_ENABLED=0`). Todo subprocesso e leitor serial é injetável para testes offline.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import subprocess
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import click

DEFAULT_CHIP = "esp32s3"
DEFAULT_FLASH_SIZE = 0x1000000
DEFAULT_PIO_ENV = "twatch-s3-plus"
NO_LORA_FLAG = "-DYBY_LORA_ENABLED=0"
SERIAL_BAUD = 115200
EXIT_FAILURE = 1
EXIT_CRASH = 2
EXIT_MONITOR_ERROR = 3

_PORT_PATTERN = re.compile(r"^(?:/dev/(?:tty|cu\.)[A-Za-z0-9_.\-]+|COM\d{1,3})$")
_ENV_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_SECRET = re.compile(
    r"(?i)\b(pass(?:word|wd)?|psk|token|secret|api[_-]?key|authorization)\b(\s*[=:]\s*)[^\s,;]+"
)

CRASH_SIGNATURES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Guru Meditation Error", re.compile(r"Guru Meditation Error")),
    ("Backtrace:", re.compile(r"Backtrace:")),
    ("LoadProhibited", re.compile(r"LoadProhibited")),
    ("StoreProhibited", re.compile(r"StoreProhibited")),
    ("InstrFetchProhibited", re.compile(r"InstrFetchProhibited")),
    ("Stack canary watchpoint triggered", re.compile(r"Stack canary watchpoint triggered")),
    ("abort() was called", re.compile(r"abort\(\) was called")),
    ("Brownout detector was triggered", re.compile(r"Brownout detector was triggered")),
)
_WDT_RESET = re.compile(r"rst:0x[0-9a-fA-F]+\s*\([A-Z0-9_]*(?:WDT|PANIC|BROWNOUT)[A-Z0-9_]*\)")
_BACKTRACE_LINE = re.compile(
    r"Backtrace:|^\s*#\d+\s+0x[0-9a-fA-F]+|0x[0-9a-fA-F]{8}:0x[0-9a-fA-F]{8}"
)


@dataclass(frozen=True)
class RunResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class Runner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float = 600.0,
    ) -> RunResult: ...


class SerialReader(Protocol):
    def read_lines(self, port: str, baud: int, seconds: float) -> list[str]: ...


class SubprocessRunner:
    """Executa comandos sem shell; `env` é mesclado sobre `os.environ`."""

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float = 600.0,
    ) -> RunResult:
        merged = {**os.environ, **(env or {})}
        try:
            proc = subprocess.run(  # noqa: S603 - argv fixo, sem shell
                list(argv),
                cwd=cwd,
                env=merged,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except FileNotFoundError:
            return RunResult(127, "", f"comando não encontrado: {argv[0]}")
        except subprocess.TimeoutExpired:
            return RunResult(124, "", f"timeout após {timeout:.0f}s: {argv[0]}")
        return RunResult(proc.returncode, proc.stdout or "", proc.stderr or "")


class PySerialReader:
    """Leitor serial real sobre `pyserial` (import preguiçoso)."""

    def read_lines(self, port: str, baud: int, seconds: float) -> list[str]:
        serial = importlib.import_module("serial")
        deadline = time.monotonic() + seconds
        buffer = b""
        with serial.Serial(port, baud, timeout=0.5) as handle:
            while time.monotonic() < deadline:
                buffer += handle.read(1024)
        return buffer.decode("utf-8", errors="replace").splitlines()


@dataclass
class FlashContext:
    runner: Runner = field(default_factory=SubprocessRunner)
    serial_reader: SerialReader = field(default_factory=PySerialReader)


def redact(text: str) -> str:
    """Remove ANSI/controle e valores de segredos (ex.: senha Wi-Fi impressa no log)."""

    cleaned = _CONTROL.sub("", _ANSI.sub("", text))
    return _SECRET.sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTED]", cleaned)


def esptool_binary(environ: Mapping[str, str] | None = None) -> str:
    return (environ if environ is not None else os.environ).get("YBY_ESPTOOL_BIN") or "esptool.py"


def parse_size(value: str | int) -> int:
    size = value if isinstance(value, int) else int(str(value), 0)
    if size <= 0 or size % 0x1000:
        raise ValueError("flash-size deve ser positivo e múltiplo de 0x1000")
    return size


def validate_port(port: str) -> str:
    if not _PORT_PATTERN.match(port):
        raise ValueError("porta serial inválida (ex.: /dev/ttyACM0 ou COM3)")
    return port


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def run_backup(
    ctx: FlashContext,
    *,
    port: str,
    out: Path,
    flash_size: int = DEFAULT_FLASH_SIZE,
    force: bool = False,
) -> dict[str, Any]:
    """Lê a flash inteira (`read_flash 0x0 <size>`) e grava `.sha256` e `.json` ao lado."""

    validate_port(port)
    flash_size = parse_size(flash_size)
    if out.exists() and not force:
        return {"status": "backup_failed", "error": f"{out.name} já existe (use --force)"}
    out.parent.mkdir(parents=True, exist_ok=True)

    argv = [
        esptool_binary(),
        "--chip",
        DEFAULT_CHIP,
        "--port",
        port,
        "read_flash",
        "0x0",
        hex(flash_size),
        str(out),
    ]
    result = ctx.runner.run(argv, timeout=900.0)
    if result.returncode != 0:
        return {
            "status": "backup_failed",
            "returncode": result.returncode,
            "error": redact(result.stderr or result.stdout)[-1000:],
            "argv": argv,
        }
    if not out.is_file():
        return {"status": "backup_failed", "error": "esptool não gerou o arquivo", "argv": argv}

    size_bytes = out.stat().st_size
    digest = sha256_file(out)
    sidecar = out.with_name(out.name + ".sha256")
    manifest_path = out.with_name(out.name + ".json")
    sidecar.write_text(f"{digest}  {out.name}\n", encoding="utf-8")
    manifest: dict[str, Any] = {
        "status": "ok" if size_bytes == flash_size else "size_mismatch",
        "chip": DEFAULT_CHIP,
        "port": port,
        "file": str(out),
        "size_bytes": size_bytes,
        "expected_bytes": flash_size,
        "sha256": digest,
        "sha256_file": str(sidecar),
        "manifest_file": str(manifest_path),
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "argv": argv,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def detect_crash(lines: Sequence[str]) -> tuple[list[str], list[str], int | None]:
    """Retorna (padrões, linhas de backtrace, índice da primeira linha de crash)."""

    patterns: list[str] = []
    first_index: int | None = None
    for index, line in enumerate(lines):
        for name, regex in CRASH_SIGNATURES:
            if regex.search(line) and name not in patterns:
                patterns.append(name)
                first_index = index if first_index is None else first_index
        wdt = _WDT_RESET.search(line)
        if wdt:
            label = wdt.group(0)
            if label not in patterns:
                patterns.append(label)
            first_index = index if first_index is None else first_index
    backtrace = [line.strip() for line in lines if _BACKTRACE_LINE.search(line)][:50]
    return patterns, backtrace, first_index


def _excerpt(lines: Sequence[str], first_crash: int | None, limit: int = 40) -> str:
    if first_crash is None:
        window = list(lines)[-limit:]
    else:
        start = max(0, first_crash - 3)
        window = list(lines)[start : start + limit]
    return "\n".join(window)[-4000:]


def run_build_and_flash(
    ctx: FlashContext,
    *,
    project_dir: Path,
    port: str,
    env_name: str = DEFAULT_PIO_ENV,
    monitor_seconds: float = 10.0,
    baud: int = SERIAL_BAUD,
) -> dict[str, Any]:
    """Compila/grava via PlatformIO (sem LoRa) e monitora a serial em busca de crashes."""

    validate_port(port)
    if not _ENV_PATTERN.match(env_name):
        raise ValueError("nome de ambiente PlatformIO inválido")
    if monitor_seconds < 0:
        raise ValueError("monitor-seconds não pode ser negativo")
    if not (project_dir / "platformio.ini").is_file():
        return {
            "status": "flash_failed",
            "crash_detected": False,
            "patterns": [],
            "backtrace_lines": [],
            "serial_excerpt": "",
            "error": "platformio.ini não encontrado em --project-dir",
        }

    existing = os.environ.get("PLATFORMIO_BUILD_FLAGS", "").strip()
    build_flags = f"{existing} {NO_LORA_FLAG}".strip()
    argv = ["pio", "run", "-e", env_name, "-t", "upload", "--upload-port", port]
    base: dict[str, Any] = {
        "env": env_name,
        "port": port,
        "build_flags": build_flags,
        "lora_enabled": False,
        "monitor_seconds": monitor_seconds,
        "argv": argv,
    }

    result = ctx.runner.run(
        argv,
        cwd=project_dir,
        env={"PLATFORMIO_BUILD_FLAGS": build_flags},
        timeout=1800.0,
    )
    if result.returncode != 0:
        return {
            **base,
            "status": "flash_failed",
            "crash_detected": False,
            "patterns": [],
            "backtrace_lines": [],
            "serial_excerpt": "",
            "returncode": result.returncode,
            "error": redact(result.stderr or result.stdout)[-2000:],
        }

    lines: list[str] = []
    if monitor_seconds > 0:
        try:
            raw_lines = ctx.serial_reader.read_lines(port, baud, monitor_seconds)
            lines = [redact(line) for line in raw_lines]
        except Exception as exc:  # noqa: BLE001 - pyserial ausente, porta ocupada etc.
            return {
                **base,
                "status": "monitor_error",
                "crash_detected": False,
                "patterns": [],
                "backtrace_lines": [],
                "serial_excerpt": "",
                "error": redact(str(exc))[:300],
            }

    patterns, backtrace, first_crash = detect_crash(lines)
    crashed = bool(patterns)
    return {
        **base,
        "status": "crash_detected" if crashed else "ok",
        "crash_detected": crashed,
        "patterns": patterns,
        "backtrace_lines": backtrace,
        "serial_excerpt": _excerpt(lines, first_crash),
    }


def _exit_code(report: Mapping[str, Any]) -> int:
    status = report.get("status")
    if status == "ok":
        return 0
    if status == "crash_detected":
        return EXIT_CRASH
    if status == "monitor_error":
        return EXIT_MONITOR_ERROR
    return EXIT_FAILURE


def _emit(report: Mapping[str, Any]) -> None:
    click.echo(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(_exit_code(report))


def _context(click_ctx: click.Context) -> FlashContext:
    obj = click_ctx.obj
    return obj if isinstance(obj, FlashContext) else FlashContext()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def cli() -> None:
    """Backup, dump e flash do LILYGO T-Watch S3 Plus (ESP32-S3)."""


@cli.command()
@click.option("--port", required=True, help="Porta serial/USB, ex.: /dev/ttyACM0")
@click.option("--out", "out", required=True, type=click.Path(path_type=Path, dir_okay=False))
@click.option("--flash-size", default=hex(DEFAULT_FLASH_SIZE), show_default=True)
@click.option("--force", is_flag=True, help="Sobrescreve um backup existente")
@click.pass_context
def backup(click_ctx: click.Context, port: str, out: Path, flash_size: str, force: bool) -> None:
    """Faz dump completo da flash e grava SHA-256 (.sha256) e manifesto (.json)."""

    try:
        report = run_backup(
            _context(click_ctx), port=port, out=out, flash_size=parse_size(flash_size), force=force
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    _emit(report)


@cli.command("build-and-flash")
@click.option(
    "--project-dir",
    required=True,
    type=click.Path(path_type=Path, exists=True, file_okay=False),
)
@click.option("--port", required=True, help="Porta serial/USB, ex.: /dev/ttyACM0")
@click.option("--env", "env_name", default=DEFAULT_PIO_ENV, show_default=True)
@click.option("--monitor-seconds", default=10.0, show_default=True, type=click.FloatRange(min=0))
@click.option("--baud", default=SERIAL_BAUD, show_default=True, type=int)
@click.pass_context
def build_and_flash(
    click_ctx: click.Context,
    project_dir: Path,
    port: str,
    env_name: str,
    monitor_seconds: float,
    baud: int,
) -> None:
    """Compila e grava com PlatformIO (sem LoRa) e monitora a serial por crashes."""

    try:
        report = run_build_and_flash(
            _context(click_ctx),
            project_dir=project_dir,
            port=port,
            env_name=env_name,
            monitor_seconds=monitor_seconds,
            baud=baud,
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    _emit(report)


if __name__ == "__main__":
    cli()
