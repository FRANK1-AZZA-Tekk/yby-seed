from unittest.mock import MagicMock, patch

from src.yby_seed.config import get_settings
from src.yby_seed.sandbox import ValidationResult, execute_validated
from src.yby_seed.sandbox.hardware_linter import analyze_hardware, lint_gpio, modbus_crc16
from src.yby_seed.sandbox.sandbox import _run_docker


def test_gpio_xiao_and_p4_reserved_pins() -> None:
    for board in ("seeed_xiao_esp32s3", "esp32_p4_c6"):
        ok, issues = lint_gpio("gpio_num_t led = GPIO_NUM_26;", board)
        assert ok is False
        assert issues


def test_modbus_crc16() -> None:
    payload = bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01])
    assert modbus_crc16(payload) == 0x0A84


def test_sandbox_removes_container_on_failure() -> None:
    mock_container = MagicMock()
    mock_container.wait.side_effect = TimeoutError("timeout")
    mock_client = MagicMock()
    mock_client.containers.create.return_value = mock_container

    with patch("docker.from_env", return_value=mock_client):
        ok, _stdout, _stderr = _run_docker(
            "img", "echo", __import__("pathlib").Path("/tmp"), get_settings()
        )
    assert ok is False
    mock_container.remove.assert_called_with(force=True)


@patch("src.yby_seed.sandbox.sandbox.shutil.which", return_value="/usr/bin/docker")
@patch("src.yby_seed.sandbox.sandbox._run_docker", return_value=(True, "ok", ""))
def test_python_runner_integration(mock_run, _which) -> None:
    result = execute_validated(
        language="python",
        code="def f():\n    return 1\n",
        filename="main.py",
        domain="python_fastapi",
    )
    assert isinstance(result, ValidationResult)
    assert result.success is True


def test_hardware_report_pinning() -> None:
    report = analyze_hardware('#include "esp_log.h"', domain="esp_idf").to_dict()
    assert "pinning_approved" in report
