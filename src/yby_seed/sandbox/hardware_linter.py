"""Lint de hardware (GPIO) e Modbus RTU determinístico."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

BOARD_IDS = ("seeed_xiao_esp32s3", "esp32_s3_devkitc1", "esp32_p4_c6", "waveshare_modbus_rtu")

# Restrições físicas simplificadas (YBY SEED — Function Over Form)
BOARD_CONSTRAINTS: dict[str, dict[str, set[int]]] = {
    "seeed_xiao_esp32s3": {
        "reserved_flash_psram": {26, 27, 28, 29, 30, 31, 32, 33, 34},
        "strapping_critical": {0, 45, 46},
        "usb_uart": {21, 22},
    },
    "esp32_s3_devkitc1": {
        "reserved_flash_psram": {26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36},
        "strapping_critical": {0, 3, 45, 46},
        "usb_uart": {19, 20},
    },
    "esp32_p4_c6": {
        "reserved_flash_psram": {24, 25, 26, 27, 28, 29, 30},
        "strapping_critical": {0, 46},
        "usb_uart": {16, 17},
    },
    "waveshare_modbus_rtu": {
        "reserved_flash_psram": {6, 7, 8, 9, 10, 11},
        "strapping_critical": {0, 45, 46},
        "rs485": {17, 18},
    },
}

VALID_MODBUS_BAUDRATES = {1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200}
VALID_MODBUS_FUNCTIONS = {1, 2, 3, 4, 5, 6, 15, 16, 23}

_GPIO_PATTERNS = (
    re.compile(r"\bGPIO_NUM_(\d+)\b"),
    re.compile(r"\bgpio_num_t\s+([A-Za-z0-9_]+)\s*=\s*GPIO_NUM_(\d+)"),
    re.compile(r"#define\s+([A-Z0-9_]+)\s+(\d{1,2})\b"),
    re.compile(r"pin(?:Mode|mode)?\s*\(\s*(\d+)\s*,"),
    re.compile(r"digital(?:Write|Read)\s*\(\s*(\d+)\s*,"),
)


def modbus_crc16(payload: bytes) -> int:
    crc = 0xFFFF
    for byte in payload:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def _extract_gpio_assignments(code: str) -> dict[int, list[str]]:
    uses: dict[int, list[str]] = {}
    for pattern in _GPIO_PATTERNS:
        for match in pattern.finditer(code):
            if match.lastindex and match.lastindex >= 1:
                pin_raw = match.group(match.lastindex)
                try:
                    pin = int(pin_raw)
                except ValueError:
                    continue
                uses.setdefault(pin, []).append(match.group(0))
    return uses


def _detect_board(code: str, default: str = "esp32_s3_devkitc1") -> str:
    lowered = code.lower()
    for board in BOARD_IDS:
        if board in lowered:
            return board
    return default


@dataclass
class HardwareLintReport:
    board: str
    gpio_ok: bool
    gpio_issues: list[str] = field(default_factory=list)
    modbus_ok: bool = True
    modbus_issues: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "board": self.board,
            "gpio_ok": self.gpio_ok,
            "gpio_issues": self.gpio_issues,
            "modbus_ok": self.modbus_ok,
            "modbus_issues": self.modbus_issues,
            "pinning_approved": self.gpio_ok and self.modbus_ok,
        }


def lint_gpio(code: str, board: str) -> tuple[bool, list[str]]:
    issues: list[str] = []
    constraints = BOARD_CONSTRAINTS.get(board, BOARD_CONSTRAINTS["esp32_s3_devkitc1"])
    reserved = constraints.get("reserved_flash_psram", set())
    strapping = constraints.get("strapping_critical", set())
    special = set()
    for key, values in constraints.items():
        if key not in {"reserved_flash_psram", "strapping_critical"}:
            special.update(values)

    assignments = _extract_gpio_assignments(code)
    for pin, refs in assignments.items():
        if len(refs) > 1:
            issues.append(f"GPIO {pin} atribuído múltiplas vezes: {refs}")
        if pin in reserved:
            issues.append(f"GPIO {pin} reservado Flash/PSRAM na placa {board}")
        if pin in strapping:
            issues.append(f"GPIO {pin} é strapping crítico em {board}")
    return len(issues) == 0, issues


def lint_modbus_rtu(code: str) -> tuple[bool, list[str]]:
    issues: list[str] = []

    baud_matches = re.findall(r"baud(?:rate)?\s*[=:]\s*(\d+)", code, flags=re.I)
    for baud in baud_matches:
        if int(baud) not in VALID_MODBUS_BAUDRATES:
            issues.append(f"baudrate inválido: {baud}")

    slave_matches = re.findall(r"slave(?:_id|_address)?\s*[=:]\s*(\d+)", code, flags=re.I)
    for slave in slave_matches:
        slave_id = int(slave)
        if slave_id < 1 or slave_id > 247:
            issues.append(f"endereço slave fora do range 1-247: {slave_id}")

    fn_matches = re.findall(r"function(?:_code)?\s*[=:]\s*0x([0-9A-Fa-f]+)", code)
    fn_matches += re.findall(r"function(?:_code)?\s*[=:]\s*(\d+)", code, flags=re.I)
    for fn in fn_matches:
        fn_code = int(fn, 16) if "x" in fn.lower() else int(fn)
        if fn_code not in VALID_MODBUS_FUNCTIONS:
            issues.append(f"function code não suportado: {fn_code}")

    hex_frames = re.findall(r"\b([0-9A-Fa-f]{4,})\b", code)
    for frame_hex in hex_frames[:5]:
        if len(frame_hex) % 2 != 0:
            continue
        try:
            raw = bytes.fromhex(frame_hex)
        except ValueError:
            continue
        if len(raw) < 4:
            continue
        body, crc_le = raw[:-2], int.from_bytes(raw[-2:], "little")
        expected = modbus_crc16(body)
        if crc_le != expected:
            issues.append(
                f"CRC16 inválido no frame {frame_hex}: esperado {expected:04X}, encontrado {crc_le:04X}"
            )

    return len(issues) == 0, issues


def analyze_hardware(code: str, *, domain: str, board: str | None = None) -> HardwareLintReport:
    selected_board = board or _detect_board(code)
    gpio_ok, gpio_issues = lint_gpio(code, selected_board)

    modbus_ok, modbus_issues = True, []
    if domain in {"modbus_rtu", "waveshare_modbus_rtu"} or "modbus" in code.lower():
        modbus_ok, modbus_issues = lint_modbus_rtu(code)

    return HardwareLintReport(
        board=selected_board,
        gpio_ok=gpio_ok,
        gpio_issues=gpio_issues,
        modbus_ok=modbus_ok,
        modbus_issues=modbus_issues,
    )
