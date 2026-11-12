"""deploy_model — pré-voo ChatML e registro Ollama."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.yby_seed.forge import deploy_model


def _valid_record(user: str = "intenção", assistant: str = "def ok(): pass") -> dict:
    return {
        "messages": [
            {"role": "system", "content": "YBY SEED"},
            {"role": "user", "content": user},
            {"role": "assistant", "content": assistant},
        ]
    }


def test_preflight_valid_chatml_passes(tmp_path: Path) -> None:
    path = tmp_path / "validated_pairs.jsonl"
    path.write_text(json.dumps(_valid_record()) + "\n", encoding="utf-8")
    report = deploy_model.preflight_dataset(path, min_samples=1)
    assert report.ok
    assert report.valid_count == 1
    assert not report.line_errors


def test_preflight_invalid_json_blocked(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text("{not json\n", encoding="utf-8")
    report = deploy_model.preflight_dataset(path, min_samples=1)
    assert not report.ok
    assert any("JSON inválido" in e for e in report.line_errors)


def test_preflight_empty_assistant_blocked(tmp_path: Path) -> None:
    rec = _valid_record(assistant="   ")
    path = tmp_path / "validated_pairs.jsonl"
    path.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    report = deploy_model.preflight_dataset(path, min_samples=1)
    assert not report.ok
    assert any("content vazio" in e for e in report.line_errors)


def test_preflight_token_overflow_blocked(tmp_path: Path) -> None:
    huge = "x" * (deploy_model.MAX_TOKENS_ESTIMATE * 4 + 8)
    rec = _valid_record(assistant=huge)
    path = tmp_path / "validated_pairs.jsonl"
    path.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    report = deploy_model.preflight_dataset(path, min_samples=1)
    assert not report.ok
    assert any("tokens" in e for e in report.line_errors)


def test_build_modelfile_contains_chatml_and_params(tmp_path: Path) -> None:
    gguf = tmp_path / "model.gguf"
    gguf.write_bytes(b"GGUF\x00\x00\x00")
    text = deploy_model.build_modelfile_content(gguf)
    assert "PARAMETER num_ctx 4096" in text
    assert "PARAMETER temperature 0.1" in text
    assert "<|im_start|>system" in text
    assert "docs/yby_seed_contracts.md" in text
    assert str(gguf.resolve()) in text


def test_register_gguf_dry_run_no_subprocess(tmp_path: Path) -> None:
    gguf = tmp_path / "YBY-SEED-Coder-7B-IQ4_XS.gguf"
    gguf.write_bytes(b"GGUF" + b"\x00" * 128)
    with patch.object(deploy_model.subprocess, "run", MagicMock()) as mock_run:
        report = deploy_model.register_gguf_in_ollama(
            gguf,
            dry_run=True,
            modelfile_dir=tmp_path,
        )
    mock_run.assert_not_called()
    assert not report.errors
    assert "FROM" in report.modelfile_text


def test_register_gguf_calls_ollama_create(tmp_path: Path) -> None:
    gguf = tmp_path / "small.gguf"
    gguf.write_bytes(b"GGUF" + b"\x00" * 64)
    mock_proc = MagicMock(returncode=0, stdout="done", stderr="")
    with patch.object(deploy_model.subprocess, "run", return_value=mock_proc) as mock_run:
        report = deploy_model.register_gguf_in_ollama(
            gguf,
            model_name="yby-seed-coder:latest",
            modelfile_dir=tmp_path,
        )
    assert report.created
    mock_run.assert_called_once()
    args = mock_run.call_args[0][0]
    assert args[0:3] == ["ollama", "create", "yby-seed-coder:latest"]


def test_verify_gguf_blocks_oversized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(deploy_model, "GGUF_BLOCK_BYTES", 16)
    gguf = tmp_path / "huge.gguf"
    gguf.write_bytes(b"GGUF" + b"\x00" * 32)
    warnings, blockers = deploy_model.verify_gguf_file(gguf)
    assert blockers
    assert isinstance(warnings, list)
