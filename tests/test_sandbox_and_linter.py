from unittest.mock import MagicMock, patch

from src.yby_seed.config import get_settings
from src.yby_seed.sandbox import ValidationResult, execute_validated
from src.yby_seed.sandbox.hardware_linter import (
    analyze_hardware,
    lint_adc2_wifi_conflict,
    lint_bus_pin_collisions,
    lint_gpio,
    lint_rs485_de_re,
    modbus_crc16,
)
from src.yby_seed.sandbox.sandbox import (
    FALLBACK_SANDBOX_IMAGE,
    _run_docker,
    resolve_sandbox_python_image,
)


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


def test_adc2_wifi_conflict_detected() -> None:
    code = "WiFi.begin();\nint x = analogRead(35);\n"
    ok, issues = lint_adc2_wifi_conflict(code)
    assert ok is False
    assert any("ADC2" in i for i in issues)


def test_i2c_spi_pin_collision() -> None:
    code = "int SDA = 21;\nint MOSI = 21;\n"
    ok, issues = lint_bus_pin_collisions(code)
    assert ok is False
    assert any("I2C" in i and "SPI" in i for i in issues)


def test_rs485_requires_de_re() -> None:
    code = "// board: waveshare_modbus_rtu\nmodbus_rtu_init();\n"
    ok, issues = lint_rs485_de_re(code, "waveshare_modbus_rtu")
    assert ok is False
    assert any("DE/RE" in i for i in issues)


@patch("src.yby_seed.sandbox.sandbox.resources.get_docker_client_sync")
def test_resolve_sandbox_prefers_warm_image(mock_client: MagicMock) -> None:
    from src.yby_seed.sandbox.sandbox import FALLBACK_SANDBOX_IMAGE, resolve_sandbox_python_image

    mock_client.return_value.images.get.side_effect = lambda name: name
    with patch("src.yby_seed.sandbox.sandbox.shutil.which", return_value="/usr/bin/docker"):
        assert resolve_sandbox_python_image(get_settings()) == "yby-sandbox:latest"
    mock_client.return_value.images.get.side_effect = Exception("missing")
    with patch("src.yby_seed.sandbox.sandbox.shutil.which", return_value="/usr/bin/docker"):
        assert resolve_sandbox_python_image(get_settings()) == FALLBACK_SANDBOX_IMAGE


def test_resolve_sandbox_image_without_docker(monkeypatch) -> None:
    monkeypatch.setattr("src.yby_seed.sandbox.sandbox.shutil.which", lambda _: None)
    image = resolve_sandbox_python_image(get_settings())
    assert "sandbox" in image or image == FALLBACK_SANDBOX_IMAGE
