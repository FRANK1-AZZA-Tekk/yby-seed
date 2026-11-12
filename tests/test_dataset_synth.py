"""Dataset sintético — sandbox obrigatório e dedupe SHA-256."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.yby_seed.config import Settings
from src.yby_seed.forge import dataset_synth
from src.yby_seed.sandbox import ValidationResult

GOOD_ASSISTANT = (
    "```yaml\nhardware_check:\n  board: esp32_s3_devkitc1\n  domain: esp_idf\n```\n"
    "```c\n// board: esp32_s3_devkitc1\n"
    '#include "freertos/FreeRTOS.h"\nvoid app_main(void) {}\n```'
)

BAD_ASSISTANT = "```yaml\nhardware_check:\n  board: x\n```\n```c\nbroken\n```"


@pytest.mark.asyncio
async def test_rejected_candidates_not_persisted(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "validated_pairs.jsonl"
    def settings_fn() -> Settings:
        return Settings(datasets_path=out)

    monkeypatch.setattr("src.yby_seed.forge.dataset_synth.get_settings", settings_fn)

    def side_effect(**kwargs):
        code = kwargs.get("code", "")
        if "broken" in code:
            return ValidationResult(False, "", "lint", {})
        return ValidationResult(True, "ok", "", {"hardware": {"pinning_approved": True}})

    args = dataset_synth.build_parser().parse_args(
        ["--count", "1", "--domain", "esp_idf", "--max-failures", "5"]
    )
    with (
        patch(
            "src.yby_seed.forge.dataset_synth.generate_candidate",
            new=AsyncMock(side_effect=[BAD_ASSISTANT, GOOD_ASSISTANT, GOOD_ASSISTANT]),
        ),
        patch("src.yby_seed.forge.dataset_synth.execute_validated", side_effect=side_effect),
    ):
        code = await dataset_synth.run_synthesis(args)

    assert code == 0
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert BAD_ASSISTANT not in record["messages"][-1]["content"]


@pytest.mark.asyncio
async def test_dedup_skips_duplicate_hash(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "validated_pairs.jsonl"
    def settings_fn() -> Settings:
        return Settings(datasets_path=out)

    monkeypatch.setattr("src.yby_seed.forge.dataset_synth.get_settings", settings_fn)

    ok = ValidationResult(True, "", "", {"hardware": {"pinning_approved": True}})
    args = dataset_synth.build_parser().parse_args(
        ["--count", "2", "--domain", "esp_idf", "--max-failures", "10"]
    )
    with (
        patch(
            "src.yby_seed.forge.dataset_synth.generate_candidate",
            new=AsyncMock(return_value=GOOD_ASSISTANT),
        ),
        patch("src.yby_seed.forge.dataset_synth.execute_validated", return_value=ok),
    ):
        await dataset_synth.run_synthesis(args)

    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1


def test_parse_contract_response() -> None:
    parsed = dataset_synth.parse_contract_response(GOOD_ASSISTANT, "esp_idf")
    assert parsed is not None
    code, filename, lang = parsed
    assert lang == "cpp_embedded"
    assert "app_main" in code
    assert filename == "main.c"
