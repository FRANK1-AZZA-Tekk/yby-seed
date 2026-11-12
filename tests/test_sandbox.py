from unittest.mock import patch

from src.yby_seed.sandbox import ValidationResult, execute_validated
from src.yby_seed.sandbox.hardware_linter import analyze_hardware


def test_execute_validated_hardware_failure_before_docker() -> None:
    code = "gpio_num_t x = GPIO_NUM_26;"
    result = execute_validated(
        language="cpp_embedded",
        code=code,
        filename="main.cpp",
        domain="esp_idf",
    )
    assert isinstance(result, ValidationResult)
    assert result.success is False
    assert "hardware_linter" in result.stderr


@patch("src.yby_seed.sandbox.sandbox.shutil.which", return_value="/usr/bin/docker")
@patch("src.yby_seed.sandbox.sandbox._run_docker", return_value=(True, "ok", ""))
def test_execute_validated_python_runner_ok(mock_docker, _mock_which) -> None:
    result = execute_validated(
        language="python",
        code="def f():\n    return 1\n",
        filename="main.py",
        tests="def test_f():\n    assert f()==1\n",
        domain="python_fastapi",
    )
    assert result.success is True
    assert result.report.get("runner") == "PythonRunner"
    mock_docker.assert_called_once()


def test_embedded_analyze_in_report() -> None:
    report = analyze_hardware('#include "lvgl.h"', domain="lvgl_v9")
    assert "board" in report.to_dict()
