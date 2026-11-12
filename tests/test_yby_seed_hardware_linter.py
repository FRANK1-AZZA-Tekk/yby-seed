from src.yby_seed.sandbox.hardware_linter import (
    analyze_hardware,
    lint_gpio,
    lint_modbus_rtu,
    modbus_crc16,
)


def test_modbus_crc16_known_vector() -> None:
    payload = bytes([0x01, 0x03, 0x00, 0x00, 0x00, 0x01])
    assert modbus_crc16(payload) == 0x0A84


def test_gpio_reserved_pin_detected() -> None:
    code = "gpio_num_t led = GPIO_NUM_26;"
    ok, issues = lint_gpio(code, "esp32_s3_devkitc1")
    assert ok is False
    assert any("26" in issue for issue in issues)


def test_modbus_invalid_slave() -> None:
    code = "slave_id = 300\nbaudrate = 9600"
    ok, issues = lint_modbus_rtu(code)
    assert ok is False


def test_analyze_hardware_report_shape() -> None:
    code = "#include \"esp_log.h\"\nvoid app_main(){}"
    report = analyze_hardware(code, domain="esp_idf")
    data = report.to_dict()
    assert "board" in data
    assert "pinning_approved" in data
