"""verify_host.py — mocks determinísticos."""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("verify_host", _ROOT / "scripts" / "verify_host.py")
verify_host = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["verify_host"] = verify_host
_spec.loader.exec_module(verify_host)


def test_run_verify_all_ok() -> None:
    with (
        patch.object(verify_host, "check_vram", return_value=(True, "ok")),
        patch.object(verify_host, "check_ollama", return_value=(True, "ok")),
        patch.object(verify_host, "check_docker_container", return_value=(True, "healthy")),
        patch.object(verify_host, "check_litellm_cache", return_value=(True, "hit")),
    ):
        report = verify_host.run_verify()
    assert report.ok is True
    assert len(report.checks) >= 6


def test_run_verify_fails_on_vram() -> None:
    with (
        patch.object(verify_host, "check_vram", return_value=(False, "sem gpu")),
        patch.object(verify_host, "check_ollama", return_value=(True, "ok")),
        patch.object(verify_host, "check_docker_container", return_value=(True, "ok")),
        patch.object(verify_host, "check_litellm_cache", return_value=(True, "ok")),
    ):
        report = verify_host.run_verify()
    assert report.ok is False
