from pathlib import Path

from src.yby_seed.telemetry import collect_telemetry, count_validated_pairs


def test_count_validated_pairs_empty(tmp_path: Path) -> None:
    path = tmp_path / "validated_pairs.jsonl"
    assert count_validated_pairs(path) == 0


def test_count_validated_pairs_lines(tmp_path: Path) -> None:
    path = tmp_path / "validated_pairs.jsonl"
    path.write_text('{"a":1}\n{"b":2}\n', encoding="utf-8")
    assert count_validated_pairs(path) == 2


def test_collect_telemetry_shape(monkeypatch) -> None:
    monkeypatch.setattr(
        "src.yby_seed.telemetry.read_gpu_stats",
        lambda: {"available": False, "name": "x", "vram_used_mb": 0, "vram_total_mb": 4096, "temperature_c": 0},
    )
    monkeypatch.setattr("src.yby_seed.telemetry.read_container_status", lambda: {"postgres": "down"})
    monkeypatch.setattr(
        "src.yby_seed.telemetry.read_openrouter_spend",
        lambda: {"spent_usd": 0.0, "budget_usd": 3.5, "remaining_usd": 3.5},
    )
    monkeypatch.setattr("src.yby_seed.telemetry.count_validated_pairs", lambda _path=None: 0)

    payload = collect_telemetry()
    assert "gpu" in payload
    assert payload["containers"]["postgres"] == "down"
    assert payload["validated_pairs"] == 0
