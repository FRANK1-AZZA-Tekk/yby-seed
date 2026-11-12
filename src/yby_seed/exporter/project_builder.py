"""Exportação determinística de missões validadas para workspace/."""

from __future__ import annotations

import io
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from src.yby_seed.agents.state import MissionState, MissionStatus
from src.yby_seed.models import DomainKind

EXPORT_ROOT = Path("workspace/exports")

EMBEDDED_DOMAINS: frozenset[DomainKind] = frozenset({"esp_idf", "lvgl_v9"})
PYTHON_DOMAINS: frozenset[DomainKind] = frozenset({"python_fastapi", "modbus_rtu"})

PLATFORMIO_BOARDS: dict[str, str] = {
    "seeed_xiao_esp32s3": "seeed_xiao_esp32s3",
    "esp32_s3_devkitc1": "esp32-s3-devkitc-1",
    "esp32_p4_c6": "esp32-p4-devboard",
    "waveshare_modbus_rtu": "esp32dev",
}


def _slug(user_intent: str, mission_id: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", user_intent.lower()).strip("-")[:48]
    return cleaned or mission_id[:8]


def _resolve_board(state: MissionState, target_board: str) -> str:
    manifest = state.gpio_manifest or {}
    hw = (
        manifest.get("hardware_check")
        if isinstance(manifest.get("hardware_check"), dict)
        else manifest
    )
    if isinstance(hw, dict) and hw.get("board"):
        return str(hw["board"])
    if manifest.get("board"):
        return str(manifest["board"])
    return target_board


def _collect_pins(state: MissionState) -> list[dict[str, Any]]:
    manifest = state.gpio_manifest or {}
    hw = (
        manifest.get("hardware_check")
        if isinstance(manifest.get("hardware_check"), dict)
        else manifest
    )
    if isinstance(hw, dict) and hw.get("gpio_claims"):
        return list(hw["gpio_claims"])
    pins = manifest.get("pins") or []
    collected: list[dict[str, Any]] = []
    for item in pins:
        if isinstance(item, dict):
            collected.append(item)
    return collected


def _platformio_ini(board: str, domain: DomainKind) -> str:
    pio_board = PLATFORMIO_BOARDS.get(board, PLATFORMIO_BOARDS["esp32_s3_devkitc1"])
    framework = "espidf" if domain == "esp_idf" else "arduino"
    lib_deps = ""
    if domain == "lvgl_v9":
        lib_deps = "\nlib_deps =\n    lvgl/lvgl@^9.0.0"
    return f"""[env:release]
platform = espressif32
board = {pio_board}
framework = {framework}
monitor_speed = 115200
build_flags =
    -DYBY_BOARD="{board}"
    -DYBY_DOMAIN="{domain}"
{lib_deps}
"""


def _pinout_manifest_h(board: str, pins: list[dict[str, Any]]) -> str:
    lines = [
        "#pragma once",
        f"// YBY SEED — pinout gerado para {board}",
        f'#define YBY_BOARD_ID "{board}"',
        "",
    ]
    for entry in pins:
        gpio = entry.get("gpio", entry.get("pin", 0))
        role = entry.get("role", "gpio")
        lines.append(f"#define YBY_PIN_{str(role).upper().replace(' ', '_')} {gpio}")
    if not pins:
        lines.append("// (nenhum GPIO declarado no manifest)")
    return "\n".join(lines) + "\n"


def _wiring_md(board: str, pins: list[dict[str, Any]], domain: str) -> str:
    body = [f"# Fiação — `{board}`", "", f"Domínio: `{domain}`", ""]
    if not pins:
        body.append("_Sem pinos no manifest; revise `hardware_check` no Architect._")
    else:
        body.append("| GPIO | Função | Notas |")
        body.append("|---:|---|---|")
        for entry in pins:
            gpio = entry.get("gpio", entry.get("pin", "—"))
            role = entry.get("role", "—")
            notes = entry.get("notes", "")
            body.append(f"| {gpio} | {role} | {notes} |")
    body.append("")
    body.append("Consulte `include/pinout_manifest.h` no firmware exportado.")
    return "\n".join(body)


def _pyproject_toml(domain: DomainKind) -> str:
    deps = [
        '"fastapi>=0.115.0"',
        '"uvicorn[standard]>=0.32.0"',
    ]
    if domain == "modbus_rtu":
        deps.extend(['"pymodbus>=3.7.0"', '"pyserial>=3.5"'])
    dep_lines = ",\n    ".join(deps)
    return f"""[project]
name = "yby-export"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    {dep_lines},
]

[tool.pytest.ini_options]
pythonpath = ["."]
"""


def _env_example(domain: DomainKind) -> str:
    lines = [
        "YBY_LITELLM_BASE_URL=http://127.0.0.1:4000/v1",
        "YBY_LITELLM_API_KEY=local-dev-key",
    ]
    if domain == "modbus_rtu":
        lines.extend(
            [
                "MODBUS_PORT=/dev/ttyUSB0",
                "MODBUS_BAUDRATE=9600",
                "MODBUS_SLAVE_ID=1",
            ]
        )
    return "\n".join(lines) + "\n"


def export_validated_project(
    mission_state: MissionState,
    target_board: str,
    *,
    export_root: Path | None = None,
) -> tuple[Path, str]:
    """Materializa projeto em workspace/exports e retorna (pasta, nome do zip)."""
    if mission_state.status != MissionStatus.SUCCESS or mission_state.generated_code is None:
        raise ValueError("missão não validada ou sem código gerado")

    root = export_root or EXPORT_ROOT
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    slug = _slug(mission_state.user_intent, mission_state.mission_id)
    folder_name = f"{stamp}_{slug}"
    out_dir = root / folder_name
    out_dir.mkdir(parents=True, exist_ok=True)

    code = mission_state.generated_code
    board = _resolve_board(mission_state, target_board)
    pins = _collect_pins(mission_state)
    domain = mission_state.domain

    if domain in EMBEDDED_DOMAINS:
        (out_dir / "platformio.ini").write_text(_platformio_ini(board, domain), encoding="utf-8")
        src = out_dir / "src"
        src.mkdir(exist_ok=True)
        cpp_name = code.filename if code.filename.endswith((".cpp", ".c")) else "main.cpp"
        (src / cpp_name).write_text(code.code, encoding="utf-8")
        inc = out_dir / "include"
        inc.mkdir(exist_ok=True)
        (inc / "pinout_manifest.h").write_text(_pinout_manifest_h(board, pins), encoding="utf-8")
        (out_dir / "WIRING.md").write_text(_wiring_md(board, pins, domain), encoding="utf-8")
    elif domain in PYTHON_DOMAINS:
        (out_dir / "pyproject.toml").write_text(_pyproject_toml(domain), encoding="utf-8")
        (out_dir / "main.py").write_text(code.code, encoding="utf-8")
        tests = code.tests or "def test_smoke():\n    assert True\n"
        (out_dir / "test_main.py").write_text(tests, encoding="utf-8")
        (out_dir / ".env.example").write_text(_env_example(domain), encoding="utf-8")
    else:
        raise ValueError(f"domínio não suportado para export: {domain}")

    manifest = {
        "mission_id": mission_state.mission_id,
        "domain": domain,
        "board": board,
        "user_intent": mission_state.user_intent,
    }
    (out_dir / "yby_export_manifest.json").write_text(
        __import__("json").dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    zip_name = f"{folder_name}.zip"
    zip_path = root / zip_name
    zip_project_folder(out_dir, zip_path)
    return out_dir, zip_name


def zip_project_folder(folder: Path, dest: Path) -> Path:
    """Compacta pasta do projeto para download (disco)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(folder).as_posix())
    return dest


def zip_project_to_memory(folder: Path) -> bytes:
    """Compacta pasta em memória (útil para respostas HTTP)."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=path.relative_to(folder).as_posix())
    return buffer.getvalue()
