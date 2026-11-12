"""Regressões da auditoria pré-produção."""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

import pytest

from src.yby_seed.forge import deploy_model
from src.yby_seed.runtime.gpu_gate import inference_slot, sync_inference_slot
from src.yby_seed.sandbox.hardware_linter import BOARD_CONSTRAINTS, lint_gpio
from src.yby_seed.sandbox.sandbox import MAX_LOG_BYTES, _run_docker


def test_litellm_fallback_chain_no_self_reference() -> None:
    root = Path(__file__).resolve().parents[1] / "config" / "litellm_config.yaml"
    text = root.read_text(encoding="utf-8")
    assert "model_name: yby-tuned" in text
    assert "yby-tuned: [yby-local" in text
    assert "yby-local: [yby-cloud-coder" in text
    assert "num_ctx: 4096" in text
    assert "max_budget: 3.50" in text
    assert "qwen2.5-coder:7b-instruct-q3_K_M" in text
    assert "qwen2.5-coder:7b-instruct-q3_K_M" in text
    assert "yby-tuned: [yby-tuned" not in text


def test_gguf_blocks_above_4gb(tmp_path: Path) -> None:
    gguf = tmp_path / "big.gguf"
    with gguf.open("wb") as handle:
        handle.write(b"GGUF")
        handle.truncate(deploy_model.GGUF_BLOCK_BYTES + 1)
    _, blockers = deploy_model.verify_gguf_file(gguf)
    assert any("excede limite" in b for b in blockers)


@pytest.mark.parametrize(
    ("board", "bad_pin"),
    [
        ("seeed_xiao_esp32s3", 26),
        ("esp32_s3_devkitc1", 0),
        ("esp32_p4_c6", 46),
        ("waveshare_modbus_rtu", 17),
    ],
)
def test_hardware_linter_blocks_reserved_pins(board: str, bad_pin: int) -> None:
    reserved = BOARD_CONSTRAINTS[board].get("reserved_flash_psram", set()) | BOARD_CONSTRAINTS[
        board
    ].get("strapping_critical", set())
    code = f"// board: {board}\n#define LED {bad_pin}\npinMode({bad_pin}, OUTPUT);\n"
    ok, issues = lint_gpio(code, board=board)
    if bad_pin in reserved:
        assert not ok
        assert issues


def test_sandbox_truncates_huge_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeContainer:
        def start(self) -> None:
            pass

        def wait(self, timeout: int | None = None) -> dict[str, int]:
            return {"StatusCode": 0}

        def logs(self, stdout: bool = True, stderr: bool = False) -> bytes:
            if stdout:
                return b"x" * (MAX_LOG_BYTES + 1000)
            return b""

        def remove(self, force: bool = False) -> None:
            pass

    class FakeContainers:
        def create(self, **_kwargs) -> FakeContainer:
            return FakeContainer()

    class FakeClient:
        containers = FakeContainers()

    from src.yby_seed.config import get_settings

    monkeypatch.setattr(
        "src.yby_seed.sandbox.sandbox.resources.get_docker_client_sync",
        lambda: FakeClient(),
    )
    ok, stdout, _stderr = _run_docker("img", "true", Path("/tmp"), get_settings())
    assert ok
    assert "truncado" in stdout


@pytest.mark.asyncio
async def test_unified_gpu_lock_serializes_async_and_sync() -> None:
    order: list[str] = []
    started = threading.Event()

    def sync_holder() -> None:
        started.set()
        with sync_inference_slot():
            order.append("sync_in")

    async with inference_slot():
        order.append("async_in")
        thread = threading.Thread(target=sync_holder)
        thread.start()
        started.wait(timeout=1.0)
        await asyncio.sleep(0.05)
        order.append("async_out")
    thread.join(timeout=2.0)
    assert order == ["async_in", "async_out", "sync_in"]
