"""Varredura de portas seriais (Linux) — pyserial ou sysfs."""

from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BOARD_SUGGESTIONS: dict[str, str] = {
    "esp32-s3": "seeed_xiao_esp32s3",
    "cp210": "esp32_s3_devkitc1",
    "ch340": "esp32_s3_devkitc1",
    "ch9102": "esp32_s3_devkitc1",
    "ft232": "esp32_s3_devkitc1",
    "rs485": "waveshare_modbus_rtu",
    "modbus": "waveshare_modbus_rtu",
}


@dataclass(frozen=True)
class SerialDevice:
    path: str
    label: str
    chipset: str
    suggested_board: str | None


def _read_sysfs_id(tty_name: str) -> str:
    base = Path(f"/sys/class/tty/{tty_name}")
    if not base.is_dir():
        return ""
    device = base / "device"
    for candidate in (
        device / "idVendor",
        device / "idProduct",
        device / "manufacturer",
        device / "product",
    ):
        if candidate.is_file():
            try:
                return candidate.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
    return ""


def _classify_path(path: str, label: str = "") -> tuple[str, str | None]:
    merged = f"{path} {label}".lower()
    if "esp32" in merged and "s3" in merged:
        return "ESP32-S3", BOARD_SUGGESTIONS["esp32-s3"]
    if "cp210" in merged:
        return "CP210x", BOARD_SUGGESTIONS["cp210"]
    if "ch340" in merged or "ch910" in merged:
        return "CH340", BOARD_SUGGESTIONS["ch340"]
    if "ft232" in merged or "ftdi" in merged:
        return "FT232", BOARD_SUGGESTIONS["ft232"]
    if "rs485" in merged or "modbus" in merged:
        return "USB-RS485", BOARD_SUGGESTIONS["rs485"]
    if "acm" in path.lower():
        return "CDC-ACM", "esp32_s3_devkitc1"
    if "usb" in path.lower():
        return "USB-UART", "esp32_s3_devkitc1"
    return "serial", None


def _scan_pyserial() -> list[SerialDevice]:
    try:
        import serial.tools.list_ports
    except ImportError:
        return []

    devices: list[SerialDevice] = []
    for port in serial.tools.list_ports.comports():
        label = port.description or port.device
        chipset, board = _classify_path(port.device, f"{label} {port.manufacturer or ''}")
        devices.append(
            SerialDevice(
                path=port.device,
                label=label,
                chipset=chipset,
                suggested_board=board,
            )
        )
    return devices


def _scan_sysfs_and_globs() -> list[SerialDevice]:
    seen: set[str] = set()
    devices: list[SerialDevice] = []

    patterns = (
        "/dev/serial/by-id/*",
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
    )
    for pattern in patterns:
        for entry in sorted(glob.glob(pattern)):
            if not os.path.exists(entry):
                continue
            path = os.path.realpath(entry) if "by-id" in entry else entry
            if path in seen:
                continue
            seen.add(path)
            label = Path(entry).name if "by-id" in entry else path
            extra = ""
            tty_name = Path(path).name
            extra = _read_sysfs_id(tty_name)
            chipset, board = _classify_path(f"{entry} {path}", f"{label} {extra}")
            devices.append(
                SerialDevice(
                    path=path if path.startswith("/dev") else entry,
                    label=label,
                    chipset=chipset,
                    suggested_board=board,
                )
            )
    return devices


def scan_serial_devices_sync() -> list[SerialDevice]:
    """Varredura síncrona (Linux)."""
    devices = _scan_pyserial()
    if devices:
        return devices
    return _scan_sysfs_and_globs()


async def scan_serial_devices() -> list[SerialDevice]:
    import asyncio

    return await asyncio.to_thread(scan_serial_devices_sync)


def serial_devices_to_json(devices: list[SerialDevice]) -> list[dict[str, Any]]:
    return [
        {
            "path": d.path,
            "label": d.label,
            "chipset": d.chipset,
            "suggested_board": d.suggested_board,
        }
        for d in devices
    ]
