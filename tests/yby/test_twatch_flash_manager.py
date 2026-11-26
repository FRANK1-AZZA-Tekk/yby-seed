"""Testes 100% offline da CLI de backup/flash do T-Watch S3 Plus."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from scripts.twatch.flash_manager import (
    NO_LORA_FLAG,
    FlashContext,
    RunResult,
    cli,
    detect_crash,
    parse_size,
    redact,
    run_build_and_flash,
)

FLASH_16MB = 0x1000000

CLEAN_BOOT = [
    "ESP-ROM:esp32s3-20210327",
    "rst:0x15 (USB_UART_CHIP_RESET),boot:0x8 (SPI_FAST_FLASH_BOOT)",
    "I (123) YBY: T-Watch S3 Plus ready (lora=off)",
    "I (456) wifi: connected password=hunter2",
]
CRASH_BOOT = [
    "rst:0x1 (POWERON),boot:0x8 (SPI_FAST_FLASH_BOOT)",
    "Guru Meditation Error: Core  1 panic'ed (LoadProhibited). Exception was unhandled.",
    "Core  1 register dump:",
    "Backtrace: 0x4037a1b2:0x3fc9a2c0 0x4037f3d4:0x3fc9a2e0 0x42001234:0x3fc9a300",
    "ELF file SHA256: abcdef",
    "Rebooting...",
    "rst:0x7 (TG0WDT_SYS_RST),boot:0x8 (SPI_FAST_FLASH_BOOT)",
]


class FakeRunner:
    def __init__(self, handler: Any = None, returncode: int = 0) -> None:
        self.calls: list[dict[str, Any]] = []
        self._handler = handler
        self._returncode = returncode

    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        timeout: float = 600.0,
    ) -> RunResult:
        self.calls.append({"argv": list(argv), "cwd": cwd, "env": dict(env or {})})
        if self._handler is not None:
            self._handler(list(argv))
        stderr = "boom password=hunter2" if self._returncode else ""
        return RunResult(self._returncode, "ok", stderr)


class FakeSerial:
    def __init__(self, lines: list[str] | None = None, error: Exception | None = None) -> None:
        self.lines = lines or []
        self.error = error
        self.calls: list[tuple[str, int, float]] = []

    def read_lines(self, port: str, baud: int, seconds: float) -> list[str]:
        self.calls.append((port, baud, seconds))
        if self.error is not None:
            raise self.error
        return self.lines


def invoke(args: list[str], ctx: FlashContext) -> Any:
    return CliRunner().invoke(cli, args, obj=ctx)


def make_project(tmp_path: Path) -> Path:
    project = tmp_path / "twatch-fw"
    project.mkdir(exist_ok=True)
    (project / "platformio.ini").write_text("[env:twatch-s3-plus]\n", encoding="utf-8")
    return project


# ------------------------------------------------------------------------- backup


def test_backup_runs_esptool_read_flash_and_writes_sha256_and_manifest(tmp_path: Path) -> None:
    out = tmp_path / "backups" / "twatch_factory.bin"

    def fake_esptool(argv: list[str]) -> None:
        Path(argv[-1]).write_bytes(b"\xff" * FLASH_16MB)

    runner = FakeRunner(handler=fake_esptool)
    result = invoke(
        ["backup", "--port", "/dev/ttyACM0", "--out", str(out)],
        FlashContext(runner=runner, serial_reader=FakeSerial()),
    )

    assert result.exit_code == 0, result.output
    assert runner.calls[0]["argv"] == [
        "esptool.py",
        "--chip",
        "esp32s3",
        "--port",
        "/dev/ttyACM0",
        "read_flash",
        "0x0",
        "0x1000000",
        str(out),
    ]
    expected = hashlib.sha256(b"\xff" * FLASH_16MB).hexdigest()
    summary = json.loads(result.output)
    assert summary["status"] == "ok"
    assert summary["sha256"] == expected
    assert summary["size_bytes"] == summary["expected_bytes"] == FLASH_16MB

    sidecar = out.with_name("twatch_factory.bin.sha256")
    assert sidecar.read_text(encoding="utf-8") == f"{expected}  twatch_factory.bin\n"
    manifest = json.loads(out.with_name("twatch_factory.bin.json").read_text(encoding="utf-8"))
    assert manifest["sha256"] == expected
    assert manifest["chip"] == "esp32s3" and manifest["port"] == "/dev/ttyACM0"
    assert manifest["argv"][-2:] == ["0x1000000", str(out)]


def test_backup_custom_flash_size_and_overwrite_protection(tmp_path: Path) -> None:
    out = tmp_path / "dump.bin"
    runner = FakeRunner(handler=lambda argv: Path(argv[-1]).write_bytes(b"\x01" * 0x2000))
    ctx = FlashContext(runner=runner, serial_reader=FakeSerial())
    args = ["backup", "--port", "/dev/ttyACM0", "--out", str(out), "--flash-size", "0x2000"]

    first = invoke(args, ctx)
    assert first.exit_code == 0
    assert runner.calls[0]["argv"][-2] == "0x2000"

    again = invoke(args, ctx)
    assert again.exit_code == 1
    assert json.loads(again.output)["status"] == "backup_failed"
    assert len(runner.calls) == 1
    assert invoke([*args, "--force"], ctx).exit_code == 0
    assert len(runner.calls) == 2


def test_backup_failures_are_reported_with_non_zero_exit(tmp_path: Path) -> None:
    out = tmp_path / "dump.bin"
    failed = invoke(
        ["backup", "--port", "/dev/ttyACM0", "--out", str(out)],
        FlashContext(runner=FakeRunner(returncode=2), serial_reader=FakeSerial()),
    )
    report = json.loads(failed.output)
    assert failed.exit_code == 1 and report["status"] == "backup_failed"
    assert "hunter2" not in failed.output

    truncated = invoke(
        ["backup", "--port", "/dev/ttyACM0", "--out", str(tmp_path / "short.bin")],
        FlashContext(
            runner=FakeRunner(handler=lambda argv: Path(argv[-1]).write_bytes(b"\x00" * 16)),
            serial_reader=FakeSerial(),
        ),
    )
    assert truncated.exit_code == 1
    assert json.loads(truncated.output)["status"] == "size_mismatch"

    no_file = invoke(
        ["backup", "--port", "/dev/ttyACM0", "--out", str(tmp_path / "none.bin")],
        FlashContext(runner=FakeRunner(), serial_reader=FakeSerial()),
    )
    assert no_file.exit_code == 1


@pytest.mark.parametrize(
    "bad_port", ["--port=-x", "/dev/ttyACM0;rm -rf /", "ttyACM0", "/etc/passwd", "COM"]
)
def test_backup_rejects_unsafe_ports(tmp_path: Path, bad_port: str) -> None:
    runner = FakeRunner()
    args = ["backup", "--out", str(tmp_path / "x.bin")]
    args += [bad_port] if bad_port.startswith("--port=") else ["--port", bad_port]
    result = invoke(args, FlashContext(runner=runner, serial_reader=FakeSerial()))
    assert result.exit_code != 0
    assert runner.calls == []


def test_parse_size_validation() -> None:
    assert parse_size("0x1000000") == FLASH_16MB
    assert parse_size("8388608") == 0x800000
    for bad in ("0", "-4096", "0x1001", "abc"):
        with pytest.raises(ValueError):
            parse_size(bad)


# ------------------------------------------------------------------ build-and-flash


def test_build_and_flash_clean_boot_uses_no_lora_flag(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    runner = FakeRunner()
    serial = FakeSerial(CLEAN_BOOT)

    result = invoke(
        [
            "build-and-flash",
            "--project-dir",
            str(project),
            "--port",
            "/dev/ttyACM0",
            "--monitor-seconds",
            "3",
        ],
        FlashContext(runner=runner, serial_reader=serial),
    )

    assert result.exit_code == 0, result.output
    call = runner.calls[0]
    assert call["argv"][:2] == ["pio", "run"]
    assert ["-t", "upload"] == call["argv"][call["argv"].index("-t") : call["argv"].index("-t") + 2]
    assert call["argv"][call["argv"].index("-e") + 1] == "twatch-s3-plus"
    assert call["argv"][call["argv"].index("--upload-port") + 1] == "/dev/ttyACM0"
    assert call["cwd"] == project
    assert NO_LORA_FLAG == "-DYBY_LORA_ENABLED=0"
    assert NO_LORA_FLAG in call["env"]["PLATFORMIO_BUILD_FLAGS"].split()
    assert serial.calls == [("/dev/ttyACM0", 115200, 3.0)]

    report = json.loads(result.output)
    assert report["status"] == "ok"
    assert report["crash_detected"] is False
    assert report["patterns"] == [] and report["backtrace_lines"] == []
    assert report["lora_enabled"] is False
    assert "hunter2" not in report["serial_excerpt"]
    assert "[REDACTED]" in report["serial_excerpt"]


def test_build_and_flash_detects_guru_meditation_and_backtrace(tmp_path: Path) -> None:
    result = invoke(
        ["build-and-flash", "--project-dir", str(make_project(tmp_path)), "--port", "/dev/ttyACM0"],
        FlashContext(runner=FakeRunner(), serial_reader=FakeSerial(CRASH_BOOT)),
    )

    report = json.loads(result.output)
    assert result.exit_code == 2
    assert report["status"] == "crash_detected" and report["crash_detected"] is True
    for pattern in ("Guru Meditation Error", "Backtrace:", "LoadProhibited"):
        assert pattern in report["patterns"]
    assert any(p.startswith("rst:0x7 (TG0WDT_SYS_RST)") for p in report["patterns"])
    assert any(line.startswith("Backtrace: 0x4037a1b2") for line in report["backtrace_lines"])
    assert "Guru Meditation Error" in report["serial_excerpt"]


def test_build_and_flash_failure_returns_flash_failed(tmp_path: Path) -> None:
    serial = FakeSerial(CLEAN_BOOT)
    result = invoke(
        ["build-and-flash", "--project-dir", str(make_project(tmp_path)), "--port", "/dev/ttyACM0"],
        FlashContext(runner=FakeRunner(returncode=1), serial_reader=serial),
    )

    report = json.loads(result.output)
    assert result.exit_code == 1
    assert report["status"] == "flash_failed" and report["crash_detected"] is False
    assert "hunter2" not in report["error"]
    assert serial.calls == []


def test_build_and_flash_project_and_serial_errors(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    runner = FakeRunner()
    no_ini = invoke(
        ["build-and-flash", "--project-dir", str(empty), "--port", "/dev/ttyACM0"],
        FlashContext(runner=runner, serial_reader=FakeSerial()),
    )
    assert no_ini.exit_code == 1 and runner.calls == []

    missing = invoke(
        ["build-and-flash", "--project-dir", str(tmp_path / "nope"), "--port", "/dev/ttyACM0"],
        FlashContext(runner=runner, serial_reader=FakeSerial()),
    )
    assert missing.exit_code != 0

    broken = invoke(
        ["build-and-flash", "--project-dir", str(make_project(tmp_path)), "--port", "/dev/ttyACM0"],
        FlashContext(runner=FakeRunner(), serial_reader=FakeSerial(error=OSError("port busy"))),
    )
    assert broken.exit_code == 3
    assert json.loads(broken.output)["status"] == "monitor_error"

    skipped = invoke(
        [
            "build-and-flash",
            "--project-dir",
            str(make_project(tmp_path)),
            "--port",
            "/dev/ttyACM0",
            "--monitor-seconds",
            "0",
        ],
        FlashContext(runner=FakeRunner(), serial_reader=FakeSerial(CRASH_BOOT)),
    )
    assert skipped.exit_code == 0

    bad_env = invoke(
        [
            "build-and-flash",
            "--project-dir",
            str(make_project(tmp_path)),
            "--port",
            "/dev/ttyACM0",
            "--env",
            "x; rm -rf /",
        ],
        FlashContext(runner=FakeRunner(), serial_reader=FakeSerial()),
    )
    assert bad_env.exit_code != 0


def test_build_flags_preserve_existing_platformio_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PLATFORMIO_BUILD_FLAGS", "-DCORE_DEBUG_LEVEL=3")
    runner = FakeRunner()
    report = run_build_and_flash(
        FlashContext(runner=runner, serial_reader=FakeSerial(CLEAN_BOOT)),
        project_dir=make_project(tmp_path),
        port="/dev/ttyACM0",
        monitor_seconds=1,
    )
    assert report["status"] == "ok"
    assert runner.calls[0]["env"]["PLATFORMIO_BUILD_FLAGS"] == (
        "-DCORE_DEBUG_LEVEL=3 -DYBY_LORA_ENABLED=0"
    )


def test_detect_crash_signatures_and_clean_resets() -> None:
    for text in (
        "Guru Meditation Error: Core 0 panic'ed",
        "Backtrace: 0x400d0000:0x3ffb0000",
        "StoreProhibited",
        "InstrFetchProhibited",
        "Stack canary watchpoint triggered (loopTask)",
        "rst:0x9 (RTCWDT_SYS_RST),boot:0x8",
        "rst:0xc (PANIC_RESET),boot:0x8",
    ):
        patterns, _, first = detect_crash(["boot", text])
        assert patterns and first == 1, text
    for text in (
        "rst:0x1 (POWERON_RESET),boot:0x8",
        "rst:0x15 (USB_UART_CHIP_RESET),boot:0x8",
        "I (100) app: backtrace disabled",
    ):
        assert detect_crash([text])[0] == [], text


def test_redact_strips_ansi_and_secrets() -> None:
    cleaned = redact("\x1b[31mwifi psk=abc123 token: xyz\x1b[0m\x07")
    assert "abc123" not in cleaned and "xyz" not in cleaned and "\x1b" not in cleaned
